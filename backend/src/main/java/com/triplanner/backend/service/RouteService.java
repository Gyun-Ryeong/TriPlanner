package com.triplanner.backend.service;

import com.triplanner.backend.dto.RouteLegResponse;
import com.triplanner.backend.dto.RouteResponse;
import com.triplanner.backend.dto.TripItemResponse;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.stream.Collectors;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.web.client.HttpClientErrorException;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientException;
import org.springframework.web.server.ResponseStatusException;
import tools.jackson.databind.JsonNode;

@Service
public class RouteService {

    // Directions 15: 출발지 + 도착지 + 경유지 최대 15개
    private static final int MAX_POINTS = 17;

    // 같은 좌표에 놓인 연속 항목 묶음 (재방문 등) - 경로 계산에서는 한 지점으로 본다
    private record Stop(double lat, double lng, List<Long> itemIds) {
    }

    private final RestClient restClient = RestClient.create();
    private final TripService tripService;

    @Value("${naver.map.client-id}")
    private String clientId;

    @Value("${naver.map.client-secret}")
    private String clientSecret;

    public RouteService(TripService tripService) {
        this.tripService = tripService;
    }

    public RouteResponse getDayRoute(String email, Long tripId, Long tripDayId) {
        List<Stop> stops = groupStops(tripService.getDayItems(email, tripId, tripDayId));

        if (stops.size() < 2) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST,
                    "경로를 만들려면 서로 다른 위치의 장소가 2곳 이상 필요합니다.");
        }
        if (stops.size() > MAX_POINTS) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST,
                    "하루에 경로를 계산할 수 있는 장소는 최대 " + MAX_POINTS + "곳입니다.");
        }

        JsonNode route = requestRoute(stops);
        return toResponse(route, stops);
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
                stops.add(new Stop(item.placeLatitude(), item.placeLongitude(), ids));
            }
        }
        return stops;
    }

    private JsonNode requestRoute(List<Stop> stops) {
        String start = lngLat(stops.get(0));
        String goal = lngLat(stops.get(stops.size() - 1));
        String waypoints = stops.subList(1, stops.size() - 1).stream()
                .map(this::lngLat)
                .collect(Collectors.joining("|"));

        JsonNode root;
        try {
            root = restClient.get()
                    .uri(uriBuilder -> {
                        uriBuilder.scheme("https").host("maps.apigw.ntruss.com")
                                .path("/map-direction-15/v1/driving")
                                .queryParam("start", "{start}")
                                .queryParam("goal", "{goal}")
                                .queryParam("option", "traoptimal");
                        if (waypoints.isEmpty()) {
                            return uriBuilder.build(start, goal);
                        }
                        return uriBuilder.queryParam("waypoints", "{waypoints}")
                                .build(start, goal, waypoints);
                    })
                    .header("X-NCP-APIGW-API-KEY-ID", clientId)
                    .header("X-NCP-APIGW-API-KEY", clientSecret)
                    .retrieve()
                    .body(JsonNode.class);
        } catch (HttpClientErrorException.BadRequest e) {
            // 도로에서 먼 위치(바다·섬·산 등)처럼 Directions 가 경로를 만들 수 없는 경우 - 서버 장애와 구분한다
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST,
                    "이 장소들 사이의 자동차 경로를 찾을 수 없습니다. 도로에서 먼 위치의 장소가 있는지 확인해 주세요.");
        } catch (RestClientException e) {
            throw new ResponseStatusException(HttpStatus.BAD_GATEWAY, "길찾기 서버에서 경로를 불러오지 못했습니다.");
        }

        if (root == null || root.path("code").asInt(-1) != 0) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST,
                    "이 장소들 사이의 자동차 경로를 찾을 수 없습니다.");
        }
        return root.path("route").path("traoptimal").path(0);
    }

    private RouteResponse toResponse(JsonNode route, List<Stop> stops) {
        JsonNode summary = route.path("summary");
        int totalDistance = summary.path("distance").asInt();
        int totalDuration = summary.path("duration").asInt() / 1000;

        List<List<Double>> path = new ArrayList<>();
        for (JsonNode point : route.path("path")) {
            // Directions 는 [경도, 위도] 순서로 내려주지만 프론트에서는 [위도, 경도]가 다루기 쉽다
            path.add(List.of(point.path(1).asDouble(), point.path(0).asDouble()));
        }

        // summary.waypoints 는 경유지마다 "직전 지점부터의" 구간 거리/시간과 path 상의 위치(pointIndex)를 준다.
        // 마지막 구간(마지막 경유지 → 도착지)만 빠져 있으므로 전체에서 빼서 구한다.
        List<Integer> boundaries = new ArrayList<>();
        List<Integer> legDistances = new ArrayList<>();
        List<Integer> legDurations = new ArrayList<>();
        boundaries.add(0);
        int distanceSoFar = 0;
        int durationSoFar = 0;
        for (JsonNode waypoint : summary.path("waypoints")) {
            boundaries.add(waypoint.path("pointIndex").asInt());
            int distance = waypoint.path("distance").asInt();
            int duration = waypoint.path("duration").asInt() / 1000;
            legDistances.add(distance);
            legDurations.add(duration);
            distanceSoFar += distance;
            durationSoFar += duration;
        }
        boundaries.add(path.size() - 1);
        legDistances.add(Math.max(0, totalDistance - distanceSoFar));
        legDurations.add(Math.max(0, totalDuration - durationSoFar));

        List<RouteLegResponse> legs = new ArrayList<>();
        for (int i = 0; i < stops.size() - 1; i++) {
            List<Long> fromIds = stops.get(i).itemIds();
            List<Long> toIds = stops.get(i + 1).itemIds();
            int from = boundaries.get(i);
            int to = Math.min(boundaries.get(i + 1), path.size() - 1);
            legs.add(new RouteLegResponse(
                    fromIds.get(fromIds.size() - 1),
                    toIds.get(0),
                    legDistances.get(i),
                    legDurations.get(i),
                    new ArrayList<>(path.subList(from, to + 1))
            ));
        }

        return new RouteResponse(
                totalDistance,
                totalDuration,
                summary.path("tollFare").asInt(),
                summary.path("taxiFare").asInt(),
                summary.path("fuelPrice").asInt(),
                path,
                legs
        );
    }

    private String lngLat(Stop stop) {
        return String.format(Locale.ROOT, "%.7f,%.7f", stop.lng(), stop.lat());
    }
}
