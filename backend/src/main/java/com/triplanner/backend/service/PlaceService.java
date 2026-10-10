package com.triplanner.backend.service;

import tools.jackson.core.JacksonException;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.ObjectMapper;
import com.triplanner.backend.domain.Place;
import com.triplanner.backend.dto.PlaceResponse;
import com.triplanner.backend.dto.PlaceSaveRequest;
import com.triplanner.backend.dto.PlaceSearchResult;
import com.triplanner.backend.repository.PlaceRepository;
import java.math.BigDecimal;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.ArrayList;
import java.util.HexFormat;
import java.util.List;
import java.util.regex.Pattern;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.client.HttpClientErrorException;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientException;
import org.springframework.web.server.ResponseStatusException;
import org.springframework.web.util.HtmlUtils;

@Service
public class PlaceService {

    // 네이버 지역 검색은 한 번에 최대 5건까지만 준다 (API 제한)
    private static final int MAX_RESULTS = 5;
    static final int MAX_KEYWORD_LENGTH = 50;
    // 검색 결과 분류는 일정 항목 종류(trip_item.item_type, 20자)로도 쓰인다
    private static final int MAX_CATEGORY_LENGTH = 20;
    // 네이버 좌표(mapx, mapy)는 WGS84 경위도에 10^7 을 곱한 정수
    private static final double NAVER_COORD_SCALE = 10_000_000d;
    private static final Pattern HTML_TAG = Pattern.compile("<[^>]+>");

    private final RestClient restClient = RestClient.create();
    private final PlaceRepository placeRepository;
    private final ObjectMapper objectMapper;

    // 네이버 검색 API 는 개발자센터에서 NAVER API HUB(네이버 클라우드)로 이관되었다.
    // HUB 앱의 Client ID/Secret (naver.app) 을 쓰며, 앱에 '지역 검색' API 가 선택되어 있어야 한다
    @Value("${naver.app.client-id}")
    private String clientId;

    @Value("${naver.app.client-secret}")
    private String clientSecret;

    public PlaceService(PlaceRepository placeRepository, ObjectMapper objectMapper) {
        this.placeRepository = placeRepository;
        this.objectMapper = objectMapper;
    }

    public List<PlaceSearchResult> search(String keyword) {
        if (keyword == null || keyword.isBlank()) {
            return List.of();
        }

        if (keyword.trim().length() > MAX_KEYWORD_LENGTH) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "검색어는 " + MAX_KEYWORD_LENGTH + "자 이하로 입력해 주세요.");
        }

        JsonNode root;
        try {
            String body = restClient.get()
                    .uri(uriBuilder -> uriBuilder
                            .scheme("https").host("naverapihub.apigw.ntruss.com")
                            .path("/search/v1/local")
                            .queryParam("query", "{keyword}")
                            .queryParam("display", MAX_RESULTS)
                            .queryParam("sort", "random")
                            .build(keyword.trim()))
                    .header("X-NCP-APIGW-API-KEY-ID", clientId)
                    .header("X-NCP-APIGW-API-KEY", clientSecret)
                    .retrieve()
                    .body(String.class);
            // HUB 는 JSON 을 text/plain 으로 내려주므로 직접 파싱한다
            root = body == null ? null : objectMapper.readTree(body);
        } catch (HttpClientErrorException.BadRequest e) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "검색어를 처리할 수 없습니다. 다른 검색어로 시도해 주세요.");
        } catch (HttpClientErrorException.Unauthorized | HttpClientErrorException.Forbidden e) {
            // 키가 틀렸거나 HUB 앱에 '지역 검색' API 가 선택되지 않은 경우
            throw new ResponseStatusException(HttpStatus.BAD_GATEWAY, "장소 검색 설정에 문제가 있습니다. 관리자에게 문의해 주세요.");
        } catch (RestClientException | JacksonException e) {
            throw new ResponseStatusException(HttpStatus.BAD_GATEWAY, "네이버 장소 검색에서 장소를 불러오지 못했습니다.");
        }

        JsonNode items = root == null ? null : root.path("items");
        List<PlaceSearchResult> results = new ArrayList<>();
        if (items == null || !items.isArray()) {
            return results;
        }

        for (JsonNode item : items) {
            String name = cleanText(item.path("title").asText());
            String address = item.path("roadAddress").asText().isBlank()
                    ? item.path("address").asText()
                    : item.path("roadAddress").asText();
            Double latitude = parseCoordinate(item.path("mapy").asText());
            Double longitude = parseCoordinate(item.path("mapx").asText());
            results.add(new PlaceSearchResult(
                    naverContentId(name, address, latitude, longitude),
                    name,
                    toCategory(item.path("category").asText()),
                    address,
                    latitude,
                    longitude,
                    null
            ));
        }
        return results;
    }

    // 네이버 지역 검색은 장소 ID 를 주지 않으므로 이름·주소·좌표로 고정 ID 를 만든다
    // (같은 장소는 place 테이블에 한 번만 저장되고, TourAPI contentid 와는 'nv_' 접두어로 구분된다)
    private String naverContentId(String name, String address, Double latitude, Double longitude) {
        String source = name + "|" + address + "|" + latitude + "|" + longitude;
        try {
            byte[] hash = MessageDigest.getInstance("SHA-256").digest(source.getBytes(StandardCharsets.UTF_8));
            return "nv_" + HexFormat.of().formatHex(hash).substring(0, 40);
        } catch (NoSuchAlgorithmException e) {
            throw new IllegalStateException(e);
        }
    }

    // 네이버 분류는 '한식>육류,고기요리' 처럼 오므로 가장 구체적인 마지막 단계만 쓴다
    private String toCategory(String category) {
        if (category == null || category.isBlank()) {
            return "기타";
        }
        String last = category.substring(category.lastIndexOf('>') + 1).trim();
        return last.length() > MAX_CATEGORY_LENGTH ? last.substring(0, MAX_CATEGORY_LENGTH) : last;
    }

    // 장소 이름에는 검색어 강조용 <b> 태그와 HTML 엔티티가 섞여 온다
    private String cleanText(String text) {
        return HtmlUtils.htmlUnescape(HTML_TAG.matcher(text).replaceAll("")).trim();
    }

    private Double parseCoordinate(String value) {
        try {
            return value == null || value.isBlank() ? null : Long.parseLong(value) / NAVER_COORD_SCALE;
        } catch (NumberFormatException e) {
            return null;
        }
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

    private BigDecimal toDecimal(Double value) {
        return value == null ? null : BigDecimal.valueOf(value).setScale(7, java.math.RoundingMode.HALF_UP);
    }
}
