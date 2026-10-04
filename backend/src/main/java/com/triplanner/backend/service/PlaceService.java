package com.triplanner.backend.service;

import tools.jackson.databind.JsonNode;
import com.triplanner.backend.domain.Place;
import com.triplanner.backend.dto.PlaceResponse;
import com.triplanner.backend.dto.PlaceSaveRequest;
import com.triplanner.backend.dto.PlaceSearchResult;
import com.triplanner.backend.repository.PlaceRepository;
import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientException;
import org.springframework.web.server.ResponseStatusException;

@Service
public class PlaceService {

    // TourAPI contenttypeid → 표시용 분류명
    private static final Map<String, String> CONTENT_TYPES = Map.of(
            "12", "관광지",
            "14", "문화시설",
            "15", "축제/행사",
            "25", "여행코스",
            "28", "레포츠",
            "32", "숙박",
            "38", "쇼핑",
            "39", "음식점"
    );

    private static final int MAX_RESULTS = 20;

    private final RestClient restClient = RestClient.create();
    private final PlaceRepository placeRepository;

    @Value("${public-data.service-key}")
    private String serviceKey;

    public PlaceService(PlaceRepository placeRepository) {
        this.placeRepository = placeRepository;
    }

    public List<PlaceSearchResult> search(String keyword) {
        if (keyword == null || keyword.isBlank()) {
            return List.of();
        }

        JsonNode root;
        try {
            root = restClient.get()
                    .uri(uriBuilder -> uriBuilder
                            .scheme("https").host("apis.data.go.kr")
                            .path("/B551011/KorService2/searchKeyword2")
                            .queryParam("serviceKey", serviceKey)
                            .queryParam("MobileOS", "ETC")
                            .queryParam("MobileApp", "TriPlanner")
                            .queryParam("_type", "json")
                            .queryParam("numOfRows", MAX_RESULTS)
                            .queryParam("pageNo", 1)
                            .queryParam("keyword", "{keyword}")
                            .build(keyword.trim()))
                    .retrieve()
                    .body(JsonNode.class);
        } catch (RestClientException e) {
            throw new ResponseStatusException(HttpStatus.BAD_GATEWAY, "관광정보 서버에서 장소를 불러오지 못했습니다.");
        }

        // 결과가 없으면 TourAPI는 items 를 빈 문자열로 내려준다
        JsonNode items = root == null ? null : root.path("response").path("body").path("items").path("item");
        List<PlaceSearchResult> results = new ArrayList<>();
        if (items == null || !items.isArray()) {
            return results;
        }

        for (JsonNode item : items) {
            results.add(new PlaceSearchResult(
                    item.path("contentid").asText(),
                    item.path("title").asText(),
                    CONTENT_TYPES.getOrDefault(item.path("contenttypeid").asText(), "기타"),
                    item.path("addr1").asText(),
                    parseDoubleOrNull(item.path("mapy").asText()),
                    parseDoubleOrNull(item.path("mapx").asText()),
                    item.path("firstimage").asText()
            ));
        }
        return results;
    }

    @Transactional
    public PlaceResponse save(PlaceSaveRequest request) {
        Place place = placeRepository.findByContentId(request.contentId())
                .orElseGet(() -> placeRepository.save(new Place(
                        request.contentId(),
                        request.name(),
                        request.category(),
                        request.address(),
                        toDecimal(request.latitude()),
                        toDecimal(request.longitude()),
                        null
                )));
        return new PlaceResponse(place.getPlaceId(), place.getContentId(), place.getName());
    }

    private Double parseDoubleOrNull(String value) {
        try {
            return value == null || value.isBlank() ? null : Double.valueOf(value);
        } catch (NumberFormatException e) {
            return null;
        }
    }

    private BigDecimal toDecimal(Double value) {
        return value == null ? null : BigDecimal.valueOf(value).setScale(7, java.math.RoundingMode.HALF_UP);
    }
}
