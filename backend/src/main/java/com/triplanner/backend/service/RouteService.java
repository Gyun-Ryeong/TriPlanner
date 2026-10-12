package com.triplanner.backend.service;

import com.triplanner.backend.dto.RouteLegResponse;
import com.triplanner.backend.dto.RouteResponse;
import com.triplanner.backend.dto.TripItemResponse;
import java.time.Duration;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.stereotype.Service;
import org.springframework.web.client.HttpClientErrorException;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientException;
import org.springframework.web.server.ResponseStatusException;
import tools.jackson.databind.JsonNode;

// 하루 동선의 길찾기. 자동차(네이버 Directions)와 도보(Tmap 보행자 경로) 모두
// 1→2, 2→3, 3→4 … 장소 사이 구간마다 API 를 따로 호출해서 이어 붙인다 (경유지를 끼워 한 번에 계산하지 않는다).
@Service
public class RouteService {

    // 한 번의 길찾기에 쓸 수 있는 장소 수 (구간마다 API 를 부르므로 호출 횟수 = 장소 수 - 1 을 제한한다)
    private static final int MAX_POINTS = 17;

    private static final String TMAP_PEDESTRIAN_URL = "https://apis.openapi.sk.com/tmap/routes/pedestrian?version=1";

    // 같은 좌표에 놓인 연속 항목 묶음 (재방문 등) - 경로 계산에서는 한 지점으로 본다
    record Stop(String name, double lat, double lng, List<Long> itemIds) {
    }

    // 한 구간의 결과. 요금은 자동차일 때만 값이 있다.
    record Leg(RouteLegResponse response, int tollFare, int taxiFare, int fuelPrice) {
    }

    @FunctionalInterface
    private interface LegFetcher {
        Leg fetch(Stop from, Stop to);
    }

    // 외부 API 한 번이 오래 걸려 구간 호출 전체가 멈추지 않게 시간 제한을 둔다
    private final RestClient restClient;
    private final TripService tripService;

    @Value("${naver.map.client-id}")
    private String clientId;

    @Value("${naver.map.client-secret}")
    private String clientSecret;

    @Value("${tmap.app-key}")
    private String tmapAppKey;

    public RouteService(TripService tripService) {
        this.tripService = tripService;
        SimpleClientHttpRequestFactory requestFactory = new SimpleClientHttpRequestFactory();
        requestFactory.setConnectTimeout(Duration.ofSeconds(5));
        requestFactory.setReadTimeout(Duration.ofSeconds(10));
        this.restClient = RestClient.builder().requestFactory(requestFactory).build();
    }

    // mode: driving(자동차, 기본값) / walking(도보)
    public RouteResponse getDayRoute(String email, Long tripId, Long tripDayId, String mode) {
        boolean walking = switch (mode.toLowerCase(Locale.ROOT)) {
            case "driving" -> false;
            case "walking" -> true;
            default -> throw new ResponseStatusException(HttpStatus.BAD_REQUEST,
                    "이동 수단은 driving(자동차) 또는 walking(도보)만 선택할 수 있습니다.");
        };

        List<Stop> stops = groupStops(tripService.getDayItems(email, tripId, tripDayId));

        if (stops.size() < 2) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST,
                    "경로를 만들려면 서로 다른 위치의 장소가 2곳 이상 필요합니다.");
        }
        if (stops.size() > MAX_POINTS) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST,
                    "하루에 경로를 계산할 수 있는 장소는 최대 " + MAX_POINTS + "곳입니다.");
        }

        return walking
                ? buildRoute("WALKING", stops, this::requestWalkingLeg)
                : buildRoute("DRIVING", stops, this::requestDrivingLeg);
    }

    private List<Stop> groupStops(List<TripItemResponse> items) {
        List<Stop> stops = new ArrayList<>();
        for (TripItemResponse item : items) {
            if (item.placeLatitude() == null || item.placeLongitude() == null) {
                continue;
            }
            Stop last = stops.isEmpty() ? null : stops.get(stops.size() - 1);
            if (last != null && last.lat() == item.placeLatitude() && last.lng() == item.placeLongitude()) {
                last.itemIds().add(item.tripItemId());
            } else {
                List<Long> ids = new ArrayList<>();
                ids.add(item.tripItemId());
                String name = item.placeName() == null || item.placeName().isBlank() ? "이름 없는 장소" : item.placeName();
                stops.add(new Stop(name, item.placeLatitude(), item.placeLongitude(), ids));
            }
        }
        return stops;
    }

    // 인접한 장소 쌍마다 fetcher 를 한 번씩 호출하고, 구간 경로·거리·시간·요금을 이어 붙여 하나의 결과로 만든다
    private RouteResponse buildRoute(String mode, List<Stop> stops, LegFetcher fetcher) {
        List<RouteLegResponse> legs = new ArrayList<>();
        List<List<Double>> fullPath = new ArrayList<>();
        int totalDistance = 0;
        int totalDuration = 0;
        int tollFare = 0;
        int taxiFare = 0;
        int fuelPrice = 0;

        for (int i = 0; i < stops.size() - 1; i++) {
            Leg leg = fetcher.fetch(stops.get(i), stops.get(i + 1));
            legs.add(leg.response());
            totalDistance += leg.response().distanceMeters();
            totalDuration += leg.response().durationSeconds();
            tollFare += leg.tollFare();
            taxiFare += leg.taxiFare();
            fuelPrice += leg.fuelPrice();
            // 구간이 만나는 지점(앞 구간의 끝 = 뒤 구간의 시작)은 한 번만 넣는다
            List<List<Double>> legPath = leg.response().path();
            fullPath.addAll(fullPath.isEmpty() ? legPath : legPath.subList(1, legPath.size()));
        }

        return new RouteResponse(mode, totalDistance, totalDuration, tollFare, taxiFare, fuelPrice, fullPath, legs);
    }

    // ---- 자동차: 네이버 Directions 15 ----

    private Leg requestDrivingLeg(Stop from, Stop to) {
        JsonNode root;
        try {
            root = restClient.get()
                    .uri(uriBuilder -> uriBuilder.scheme("https").host("maps.apigw.ntruss.com")
                            .path("/map-direction-15/v1/driving")
                            .queryParam("start", "{start}")
                            .queryParam("goal", "{goal}")
                            .queryParam("option", "traoptimal")
                            .build(lngLat(from), lngLat(to)))
                    .header("X-NCP-APIGW-API-KEY-ID", clientId)
                    .header("X-NCP-APIGW-API-KEY", clientSecret)
                    .retrieve()
                    .body(JsonNode.class);
        } catch (HttpClientErrorException.BadRequest e) {
            // 도로에서 먼 위치(바다·섬·산 등)처럼 Directions 가 경로를 만들 수 없는 경우 - 서버 장애와 구분한다
            throw noRoute("자동차", from, to);
        } catch (RestClientException e) {
            throw new ResponseStatusException(HttpStatus.BAD_GATEWAY, "길찾기 서버에서 경로를 불러오지 못했습니다.");
        }

        return parseDrivingLeg(root, from, to);
    }

    static Leg parseDrivingLeg(JsonNode root, Stop from, Stop to) {
        if (root == null || root.path("code").asInt(-1) != 0) {
            throw noRoute("자동차", from, to);
        }
        JsonNode route = root.path("route").path("traoptimal").path(0);
        JsonNode summary = route.path("summary");

        List<List<Double>> path = new ArrayList<>();
        for (JsonNode point : route.path("path")) {
            // Directions 는 [경도, 위도] 순서로 내려주지만 프론트에서는 [위도, 경도]가 다루기 쉽다
            path.add(List.of(point.path(1).asDouble(), point.path(0).asDouble()));
        }
        if (path.size() < 2) {
            throw noRoute("자동차", from, to);
        }

        List<Long> fromIds = from.itemIds();
        List<Long> toIds = to.itemIds();
        RouteLegResponse leg = new RouteLegResponse(
                fromIds.get(fromIds.size() - 1),
                toIds.get(0),
                summary.path("distance").asInt(),
                summary.path("duration").asInt() / 1000,   // Directions 의 duration 은 밀리초
                path
        );
        return new Leg(leg, summary.path("tollFare").asInt(), summary.path("taxiFare").asInt(),
                summary.path("fuelPrice").asInt());
    }

    // ---- 도보: Tmap 보행자 경로 ----

    private Leg requestWalkingLeg(Stop from, Stop to) {
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("startX", from.lng());
        body.put("startY", from.lat());
        body.put("endX", to.lng());
        body.put("endY", to.lat());
        body.put("reqCoordType", "WGS84GEO");
        body.put("resCoordType", "WGS84GEO");
        // 이름은 필수 항목이지만 경로 계산에는 쓰이지 않는다 (한글은 URL 인코딩이 필요해 영문으로 고정)
        body.put("startName", "start");
        body.put("endName", "end");

        JsonNode root;
        try {
            root = restClient.post()
                    .uri(TMAP_PEDESTRIAN_URL)
                    .header("appKey", tmapAppKey)
                    .contentType(MediaType.APPLICATION_JSON)
                    .body(body)
                    .retrieve()
                    .body(JsonNode.class);
        } catch (HttpClientErrorException.BadRequest e) {
            // 바다 건너·서비스 지역 밖·너무 가까운 두 지점 등 Tmap 이 경로를 만들 수 없는 경우
            throw noRoute("도보", from, to);
        } catch (RestClientException e) {
            // 인증 오류·한도 초과·네트워크 실패 (메시지에는 요청 정보가 섞일 수 있어 로그에 남기지 않는다)
            throw new ResponseStatusException(HttpStatus.BAD_GATEWAY, "도보 길찾기 서버에서 경로를 불러오지 못했습니다.");
        }

        return new Leg(parseWalkingLeg(root, from, to), 0, 0, 0);
    }

    static RouteLegResponse parseWalkingLeg(JsonNode root, Stop from, Stop to) {
        JsonNode features = root == null ? null : root.path("features");
        if (features == null || !features.isArray() || features.isEmpty()) {
            throw noRoute("도보", from, to);
        }

        // 첫 번째 feature 의 properties 에 구간 전체의 거리(m)·시간(초)이 들어 있다
        JsonNode summary = features.get(0).path("properties");
        List<List<Double>> path = new ArrayList<>();
        for (JsonNode feature : features) {
            if (!"LineString".equals(feature.path("geometry").path("type").asString())) {
                continue;
            }
            for (JsonNode point : feature.path("geometry").path("coordinates")) {
                // Tmap 은 [경도, 위도] 순서 - 프론트에서 다루기 쉽게 [위도, 경도]로 뒤집는다
                List<Double> latLng = List.of(point.path(1).asDouble(), point.path(0).asDouble());
                // 도로 구간이 이어지는 지점의 좌표는 중복되어 오므로 직전과 같으면 건너뛴다
                if (path.isEmpty() || !path.get(path.size() - 1).equals(latLng)) {
                    path.add(latLng);
                }
            }
        }
        if (path.size() < 2) {
            throw noRoute("도보", from, to);
        }

        List<Long> fromIds = from.itemIds();
        List<Long> toIds = to.itemIds();
        return new RouteLegResponse(
                fromIds.get(fromIds.size() - 1),
                toIds.get(0),
                summary.path("totalDistance").asInt(),
                summary.path("totalTime").asInt(),
                path
        );
    }

    private static ResponseStatusException noRoute(String modeName, Stop from, Stop to) {
        return new ResponseStatusException(HttpStatus.BAD_REQUEST,
                "'" + from.name() + "' → '" + to.name() + "' 사이의 " + modeName + " 경로를 찾을 수 없습니다.");
    }

    private String lngLat(Stop stop) {
        return String.format(Locale.ROOT, "%.7f,%.7f", stop.lng(), stop.lat());
    }
}
