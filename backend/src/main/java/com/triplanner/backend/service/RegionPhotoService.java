package com.triplanner.backend.service;

import com.triplanner.backend.common.TtlCache;
import com.triplanner.backend.dto.RegionPhotoResponse;
import java.time.Duration;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientException;
import tools.jackson.databind.JsonNode;

// 지역(시·군) 대표 사진을 rag_project(/region-photo, 한국관광공사 TourAPI 사진)에서 받아 온다.
// 여행 목록을 열 때마다 부르므로 찾은 사진은 하루, 못 찾은 결과는 10분 동안 기억한다
@Service
public class RegionPhotoService {

    private static final Logger log = LoggerFactory.getLogger(RegionPhotoService.class);

    private final RestClient restClient;
    private final TtlCache<String, RegionPhotoResponse> found = new TtlCache<>(Duration.ofDays(1));
    private final TtlCache<String, RegionPhotoResponse> missing = new TtlCache<>(Duration.ofMinutes(10));

    public RegionPhotoService(@Value("${rag.base-url}") String baseUrl) {
        SimpleClientHttpRequestFactory requestFactory = new SimpleClientHttpRequestFactory();
        requestFactory.setConnectTimeout(Duration.ofSeconds(3));
        requestFactory.setReadTimeout(Duration.ofSeconds(20));
        this.restClient = RestClient.builder().baseUrl(baseUrl).requestFactory(requestFactory).build();
    }

    // name: 시·군 이름 (예: 성남, 곡성), region: 앱의 권역 이름 (같은 이름의 시군 — 고성 등 — 을 가릴 때 쓴다)
    public RegionPhotoResponse getPhoto(String name, String region) {
        String key = clean(name) + "|" + clean(region);
        RegionPhotoResponse cached = found.getIfPresent(key);
        if (cached == null) {
            cached = missing.getIfPresent(key);
        }
        if (cached != null) {
            return cached;
        }

        RegionPhotoResponse loaded = load(clean(name), clean(region));
        (loaded.image() == null ? missing : found).put(key, loaded);
        return loaded;
    }

    RegionPhotoResponse load(String name, String region) {
        if (name.isEmpty()) {
            return RegionPhotoResponse.empty();
        }
        try {
            JsonNode body = restClient.get()
                    .uri(uri -> uri.path("/region-photo").queryParam("name", name).queryParam("region", region).build())
                    .retrieve()
                    .body(JsonNode.class);
            String image = body == null ? "" : body.path("image").asText("");
            if (image.isBlank()) {
                return RegionPhotoResponse.empty();
            }
            return new RegionPhotoResponse(image, body.path("title").asText(""), body.path("credit").asText(""));
        } catch (RestClientException e) {
            // RAG 서버가 꺼져 있어도 여행 목록은 권역 사진으로 보여 준다
            log.warn("지역 사진 조회 실패 name={} cause={}", name, e.getClass().getSimpleName());
            return RegionPhotoResponse.empty();
        }
    }

    // 지역 이름은 짧다. 긴 값은 잘라서 캐시 키가 끝없이 늘지 않게 한다
    private static String clean(String value) {
        String text = value == null ? "" : value.trim();
        return text.length() > 30 ? text.substring(0, 30) : text;
    }
}
