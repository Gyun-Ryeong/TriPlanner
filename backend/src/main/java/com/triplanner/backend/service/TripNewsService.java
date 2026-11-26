package com.triplanner.backend.service;

import com.triplanner.backend.common.TtlCache;
import com.triplanner.backend.domain.Trip;
import java.time.Duration;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientException;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.node.JsonNodeFactory;
import tools.jackson.databind.node.ObjectNode;

// 여행지 소식 카드 (여행 일정 화면·알림 탭): 사건사고(여행 영향 이슈 + 화재·교통사고·사건) / 지역 소식 두 칸, 기사마다 사진.
// rag_project(/region-news)가 기사를 모으고 사진을 붙인다. 같은 지역은 15분(못 받았으면 3분) 동안 기억한다
@Service
public class TripNewsService {

    private static final Logger log = LoggerFactory.getLogger(TripNewsService.class);

    private final RestClient restClient;
    private final TripService tripService;
    private final TtlCache<String, JsonNode> found = new TtlCache<>(Duration.ofMinutes(15));
    private final TtlCache<String, JsonNode> missing = new TtlCache<>(Duration.ofMinutes(3));

    public TripNewsService(@Value("${rag.base-url}") String baseUrl, TripService tripService) {
        SimpleClientHttpRequestFactory requestFactory = new SimpleClientHttpRequestFactory();
        requestFactory.setConnectTimeout(Duration.ofSeconds(3));
        // 처음 여는 지역은 기사 수집 + 원문 사진 찾기로 수 초 걸린다
        requestFactory.setReadTimeout(Duration.ofSeconds(40));
        this.restClient = RestClient.builder().baseUrl(baseUrl).requestFactory(requestFactory).build();
        this.tripService = tripService;
    }

    // 본인 여행이 아니면 TripService 가 403/404 를 낸다
    public JsonNode getNews(String email, Long tripId) {
        Trip trip = tripService.findOwnedTrip(email, tripId);
        String region = clean(trip.getRegion());
        String name = placeName(trip.getCity(), region);
        String key = name + "|" + region;

        JsonNode cached = found.getIfPresent(key);
        if (cached == null) {
            cached = missing.getIfPresent(key);
        }
        if (cached != null) {
            return cached;
        }
        JsonNode loaded = load(name, region);
        (loaded.path("items").isEmpty() ? missing : found).put(key, loaded);
        return loaded;
    }

    // 세부 지역(도시)을 골랐으면 그 도시, 아니면 권역의 대표 도시 (날씨 알림과 같은 기준)
    static String placeName(String city, String region) {
        String c = clean(city);
        if (!c.isEmpty()) {
            return c;
        }
        RegionCatalog.RegionGrid grid = RegionCatalog.findByName(region);
        return grid != null ? grid.representative().name() : region;
    }

    JsonNode load(String name, String region) {
        if (name.isEmpty()) {
            return unavailable(name);
        }
        try {
            JsonNode body = restClient.get()
                    .uri(uri -> uri.path("/region-news").queryParam("name", name).queryParam("region", region)
                            .queryParam("limit", 6).build())  // 칸(사건사고 / 지역 소식)마다 6장
                    .retrieve()
                    .body(JsonNode.class);
            return body == null ? unavailable(name) : body;
        } catch (RestClientException e) {
            // RAG 서버가 꺼져 있어도 일정 화면은 그대로 보인다 (소식 칸에만 안내)
            log.warn("여행지 소식 조회 실패 name={} cause={}", name, e.getClass().getSimpleName());
            return unavailable(name);
        }
    }

    private static JsonNode unavailable(String name) {
        ObjectNode node = JsonNodeFactory.instance.objectNode();
        node.put("label", name);
        node.putArray("items");
        node.put("unavailable", true);
        return node;
    }

    private static String clean(String value) {
        String text = value == null ? "" : value.trim();
        return text.length() > 30 ? text.substring(0, 30) : text;
    }
}
