package com.triplanner.backend.service;

import com.triplanner.backend.common.TtlCache;
import com.triplanner.backend.dto.HolidayResponse;
import java.net.URLDecoder;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestClient;
import org.springframework.web.server.ResponseStatusException;
import tools.jackson.databind.JsonNode;

// 한국천문연구원 특일 정보(SpcdeInfoService)의 '휴일 정보'로 한 달치 공휴일을 알려준다.
// 임시공휴일·대체공휴일까지 반영되는 공식 데이터라 직접 계산하지 않는다. 같은 달은 하루 동안 기억해 두고 다시 부르지 않는다
@Service
public class HolidayService {

    private static final Logger log = LoggerFactory.getLogger(HolidayService.class);

    private final RestClient restClient;
    private final TourApiClient parser; // 공공데이터포털 응답(JSON/게이트웨이 오류) 해석을 같이 쓴다
    private final String serviceKey;
    private final TtlCache<String, Map<String, String>> cache = new TtlCache<>(Duration.ofHours(24));

    public HolidayService(TourApiClient parser, @Value("${public-data.service-key}") String serviceKey) {
        SimpleClientHttpRequestFactory requestFactory = new SimpleClientHttpRequestFactory();
        requestFactory.setConnectTimeout(Duration.ofSeconds(3));
        requestFactory.setReadTimeout(Duration.ofSeconds(8));
        this.restClient = RestClient.builder().requestFactory(requestFactory).build();
        this.parser = parser;
        this.serviceKey = serviceKey.contains("%")
                ? URLDecoder.decode(serviceKey.trim(), StandardCharsets.UTF_8) : serviceKey.trim();
    }

    public HolidayResponse getMonth(int year, int month) {
        if (year < 2000 || year > 2100 || month < 1 || month > 12) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "연도(2000~2100)와 월(1~12)을 확인해 주세요.");
        }
        String key = String.format("%d-%02d", year, month);
        Map<String, String> cached = cache.getIfPresent(key);
        if (cached != null) {
            return new HolidayResponse(year, month, cached, true);
        }
        try {
            Map<String, String> days = toDays(fetch(year, month));
            cache.put(key, days);
            return new HolidayResponse(year, month, days, true);
        } catch (RuntimeException e) {
            // 공휴일은 부가 정보라 실패해도 달력은 그대로 보여준다 (원인은 로그로만 남긴다)
            log.warn("공휴일 조회 실패 {}: {}", key, e.getMessage());
            return HolidayResponse.unavailable(year, month);
        }
    }

    private List<JsonNode> fetch(int year, int month) {
        String body = restClient.get()
                .uri(builder -> builder.scheme("https").host("apis.data.go.kr")
                        .path("/B090041/openapi/service/SpcdeInfoService/getRestDeInfo")
                        .queryParam("serviceKey", "{serviceKey}")
                        .queryParam("_type", "json")
                        .queryParam("solYear", "{year}")
                        .queryParam("solMonth", "{month}")
                        .queryParam("numOfRows", "50")
                        .build(Map.of("serviceKey", serviceKey, "year", String.valueOf(year),
                                "month", String.format("%02d", month))))
                .retrieve()
                .body(String.class);
        return parser.parseItems("getRestDeInfo", body);
    }

    // locdate(20261225) → "2026-12-25". 쉬는 날(isHoliday=Y)만 담고, 같은 날 이름이 둘이면 이어 붙인다
    static Map<String, String> toDays(List<JsonNode> items) {
        Map<String, String> days = new TreeMap<>();
        for (JsonNode item : items) {
            String date = item.path("locdate").asString("").trim();
            String name = item.path("dateName").asString("").trim();
            if (date.length() != 8 || name.isEmpty() || !"Y".equalsIgnoreCase(item.path("isHoliday").asString("Y").trim())) {
                continue;
            }
            String iso = date.substring(0, 4) + "-" + date.substring(4, 6) + "-" + date.substring(6);
            days.merge(iso, name, (a, b) -> a.equals(b) ? a : a + " · " + b);
        }
        return days;
    }
}
