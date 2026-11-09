package com.triplanner.backend.service;

import com.triplanner.backend.common.TtlCache;
import java.net.URLDecoder;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.time.YearMonth;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.ObjectMapper;

// 한국관광공사 국문 관광정보(KorService2) 호출: 축제 목록·상세·소개 정보·시도 코드.
// 하루 호출 한도가 있는 개발계정이라, 호출하는 쪽(FestivalService)이 결과를 기억해 두고 필요할 때만 부른다
@Component
public class TourApiClient {

    // 오류가 났다는 것만 알리면 되므로 원인 메시지는 로그용으로만 담는다
    public static class TourApiException extends RuntimeException {
        public TourApiException(String message) {
            super(message);
        }
    }

    static final int PAGE_SIZE = 100; // searchFestival2 가 한 번에 줄 수 있는 최대
    private static final int MAX_PAGES = 5; // 이상 응답으로 끝없이 넘기지 않으려는 상한
    private static final String PATH = "/B551011/KorService2/";

    private final RestClient restClient;
    private final ObjectMapper objectMapper;
    private final String serviceKey;
    // 시도 이름 → 법정동 시도 코드. 행정구역이 바뀌면 코드도 바뀌므로 하드코딩하지 않고 일주일에 한 번만 조회한다
    private final TtlCache<String, Map<String, String>> regionCodes = new TtlCache<>(Duration.ofDays(7));

    public TourApiClient(ObjectMapper objectMapper, @Value("${public-data.service-key}") String serviceKey) {
        SimpleClientHttpRequestFactory requestFactory = new SimpleClientHttpRequestFactory();
        requestFactory.setConnectTimeout(Duration.ofSeconds(3));
        requestFactory.setReadTimeout(Duration.ofSeconds(15));
        this.restClient = RestClient.builder().requestFactory(requestFactory).build();
        this.objectMapper = objectMapper;
        // 공공데이터포털은 '인코딩 키'(%2B 등 포함)와 '디코딩 키'를 주는데, 이중 인코딩되지 않게 항상 한 번 풀어서 쓴다
        this.serviceKey = serviceKey.contains("%")
                ? URLDecoder.decode(serviceKey.trim(), StandardCharsets.UTF_8) : serviceKey.trim();
    }

    // 그 달과 하루라도 겹치는 축제 (페이지를 넘겨 전부)
    public List<JsonNode> festivals(String regionCode, int year, int month) {
        YearMonth ym = YearMonth.of(year, month);
        List<JsonNode> all = new ArrayList<>();
        for (int page = 1; page <= MAX_PAGES; page++) {
            Map<String, String> params = new LinkedHashMap<>();
            params.put("numOfRows", String.valueOf(PAGE_SIZE));
            params.put("pageNo", String.valueOf(page));
            params.put("arrange", "C");
            params.put("lDongRegnCd", regionCode);
            params.put("eventStartDate", String.format("%d%02d01", year, month));
            params.put("eventEndDate", String.format("%d%02d%02d", year, month, ym.lengthOfMonth()));
            List<JsonNode> items = call("searchFestival2", params);
            all.addAll(items);
            if (items.size() < PAGE_SIZE) {
                break;
            }
        }
        return all;
    }

    // 소개글·홈페이지·대표 이미지 (detailCommon2). 없으면 null
    public JsonNode common(String contentId) {
        List<JsonNode> items = call("detailCommon2", Map.of("contentId", contentId, "numOfRows", "1", "pageNo", "1"));
        return items.isEmpty() ? null : items.get(0);
    }

    // 축제·행사 소개 정보 (detailIntro2, 타입 15): 프로그램·시간·요금·주최·장소. 없으면 null
    public JsonNode intro(String contentId) {
        List<JsonNode> items = call("detailIntro2",
                Map.of("contentId", contentId, "contentTypeId", "15", "numOfRows", "1", "pageNo", "1"));
        return items.isEmpty() ? null : items.get(0);
    }

    // 시도 이름 → 법정동 시도 코드 (예: 부산광역시 → 26)
    public Map<String, String> regionCodes() {
        Map<String, String> cached = regionCodes.getIfPresent("all");
        if (cached != null) {
            return cached;
        }
        Map<String, String> loaded = new LinkedHashMap<>();
        for (JsonNode item : call("ldongCode2", Map.of("numOfRows", "100", "pageNo", "1"))) {
            Map<String, String> low = new HashMap<>();
            item.properties().forEach(e -> low.put(e.getKey().toLowerCase(Locale.ROOT), e.getValue().asString("")));
            String code = firstFilled(low, "ldongregncd", "code", "regncd");
            String name = firstFilled(low, "ldongregnnm", "name", "regnnm");
            if (!code.isEmpty() && !name.isEmpty()) {
                loaded.put(name, code);
            }
        }
        if (loaded.isEmpty()) {
            throw new TourApiException("시도 코드 목록이 비어 있습니다");
        }
        regionCodes.put("all", loaded);
        return loaded;
    }

    private static String firstFilled(Map<String, String> map, String... keys) {
        for (String key : keys) {
            String value = map.get(key);
            if (value != null && !value.isBlank()) {
                return value.trim();
            }
        }
        return "";
    }

    List<JsonNode> call(String operation, Map<String, String> params) {
        String body;
        try {
            body = restClient.get()
                    .uri(builder -> {
                        builder.scheme("https").host("apis.data.go.kr").path(PATH + operation)
                                .queryParam("serviceKey", "{serviceKey}")
                                .queryParam("_type", "json")
                                .queryParam("MobileOS", "ETC")
                                .queryParam("MobileApp", "TriPlanner");
                        Map<String, String> vars = new HashMap<>(params);
                        vars.put("serviceKey", serviceKey);
                        params.keySet().forEach(k -> builder.queryParam(k, "{" + k + "}"));
                        return builder.build(vars);
                    })
                    .retrieve()
                    .body(String.class);
        } catch (RuntimeException e) {
            throw new TourApiException(operation + " 호출 실패: " + e.getClass().getSimpleName());
        }
        return parseItems(operation, body);
    }

    // 인증키 오류·한도 초과처럼 HTTP 200 으로 오는 오류도 예외로 바꾸고, 데이터 없음은 빈 목록으로 돌려준다
    List<JsonNode> parseItems(String operation, String body) {
        if (body == null || !body.trim().startsWith("{")) {
            // 게이트웨이 오류는 JSON 이 아니라 XML 로 온다 (등록되지 않은 키, 한도 초과 등)
            throw new TourApiException(operation + " 응답이 JSON 이 아닙니다 (인증키·호출 한도를 확인하세요)");
        }
        JsonNode root;
        try {
            root = objectMapper.readTree(body);
        } catch (RuntimeException e) {
            throw new TourApiException(operation + " 응답을 읽지 못했습니다");
        }
        if (root.has("OpenAPI_ServiceResponse")) {
            // 게이트웨이(공공데이터포털) 오류: 등록되지 않은 키, 한도 초과, 제공기관 서버 장애(HTTP_ERROR) 등
            JsonNode gateway = root.path("OpenAPI_ServiceResponse").path("cmmMsgHeader");
            throw new TourApiException(operation + " 게이트웨이 오류 code=" + gateway.path("returnReasonCode").asString("")
                    + " msg=" + gateway.path("errMsg").asString(""));
        }
        if (!root.has("response")) {
            throw new TourApiException(operation + " 응답 형식이 올바르지 않습니다"); // '데이터 없음'으로 착각하지 않게 오류로 처리
        }
        JsonNode header = root.path("response").path("header");
        String code = header.path("resultCode").asString("").trim();
        String message = header.path("resultMsg").asString("").toUpperCase(Locale.ROOT).replace(" ", "").replace("_", "");
        if (!code.isEmpty() && !code.equals("0000") && !code.equals("00")) {
            if (message.contains("NODATA")) {
                return List.of();
            }
            throw new TourApiException(operation + " 오류 응답 code=" + code + " msg=" + header.path("resultMsg").asString(""));
        }
        JsonNode items = root.path("response").path("body").path("items");
        JsonNode item = items.isObject() ? items.path("item") : items; // 결과가 없으면 items 가 빈 문자열로 온다
        List<JsonNode> list = new ArrayList<>();
        if (item.isArray()) {
            item.forEach(list::add);
        } else if (item.isObject()) {
            list.add(item);
        }
        return list;
    }
}
