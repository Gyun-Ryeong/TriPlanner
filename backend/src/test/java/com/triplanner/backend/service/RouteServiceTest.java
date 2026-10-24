package com.triplanner.backend.service;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

import com.triplanner.backend.dto.RouteLegResponse;
import com.triplanner.backend.dto.RouteResponse;
import java.util.ArrayList;
import java.util.List;
import org.junit.jupiter.api.Test;
import org.springframework.web.server.ResponseStatusException;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.json.JsonMapper;

class RouteServiceTest {

    private final JsonMapper mapper = JsonMapper.builder().build();

    private RouteService.Stop stop(String name, long itemId) {
        List<Long> ids = new ArrayList<>();
        ids.add(itemId);
        return new RouteService.Stop(name, 37.5, 127.0, ids);
    }

    private JsonNode json(String text) {
        return mapper.readTree(text);
    }

    @Test
    void 도보_응답에서_거리_시간_경로를_뽑고_좌표를_위도_경도_순으로_뒤집는다() {
        // Tmap: 첫 feature 의 properties 에 합계, LineString 좌표는 [경도, 위도]
        JsonNode root = json("""
                {"type":"FeatureCollection","features":[
                  {"geometry":{"type":"Point","coordinates":[127.0,37.0]},
                   "properties":{"totalDistance":1696,"totalTime":1456}},
                  {"geometry":{"type":"LineString","coordinates":[[127.0,37.0],[127.1,37.1]]},"properties":{}},
                  {"geometry":{"type":"Point","coordinates":[127.1,37.1]},"properties":{}},
                  {"geometry":{"type":"LineString","coordinates":[[127.1,37.1],[127.2,37.2]]},"properties":{}}
                ]}""");

        RouteLegResponse leg = RouteService.parseWalkingLeg(root, stop("A", 1), stop("B", 2));

        assertEquals(1696, leg.distanceMeters());
        assertEquals(1456, leg.durationSeconds());
        assertEquals(1L, leg.fromItemId());
        assertEquals(2L, leg.toItemId());
        // 구간이 이어지는 지점 (127.1, 37.1) 은 한 번만 들어간다
        assertEquals(List.of(List.of(37.0, 127.0), List.of(37.1, 127.1), List.of(37.2, 127.2)), leg.path());
    }

    @Test
    void 같은_좌표에_놓인_항목이_묶인_지점은_마지막_항목에서_나가고_첫_항목으로_들어온다() {
        JsonNode root = json("""
                {"features":[{"geometry":{"type":"LineString","coordinates":[[127.0,37.0],[127.1,37.1]]},
                  "properties":{"totalDistance":10,"totalTime":5}}]}""");
        RouteService.Stop from = stop("A", 1);
        from.itemIds().add(3L);
        RouteService.Stop to = stop("B", 2);
        to.itemIds().add(4L);

        RouteLegResponse leg = RouteService.parseWalkingLeg(root, from, to);

        assertEquals(3L, leg.fromItemId());
        assertEquals(2L, leg.toItemId());
    }

    @Test
    void 경로가_비어_있으면_구간_이름이_담긴_400() {
        ResponseStatusException e = assertThrows(ResponseStatusException.class,
                () -> RouteService.parseWalkingLeg(json("{\"features\":[]}"), stop("경복궁", 1), stop("남산타워", 2)));

        assertEquals(400, e.getStatusCode().value());
        assertEquals("'경복궁' → '남산타워' 사이의 도보 경로를 찾을 수 없습니다.", e.getReason());
    }

    @Test
    void 걸을_수_없는_구간이_있어도_나머지_구간의_경로와_합계는_남는다() {
        RouteService service = new RouteService(null);
        List<RouteService.Stop> stops = List.of(stop("A", 1), stop("B", 2), stop("C", 3));
        RouteService.LegFetcher fetcher = (from, to) -> to.name().equals("B")
                ? new RouteService.Leg(new RouteLegResponse(1L, 2L, 500, 400,
                        List.of(List.of(37.0, 127.0), List.of(37.1, 127.1)), true), 0, 0, 0)
                : RouteService.unavailableLeg(from, to);

        RouteResponse route = service.buildRoute("WALKING", stops, fetcher);

        assertEquals(2, route.legs().size());
        assertEquals(true, route.legs().get(0).available());
        assertEquals(false, route.legs().get(1).available());
        assertEquals(2L, route.legs().get(1).fromItemId());
        assertEquals(3L, route.legs().get(1).toItemId());
        assertEquals(500, route.totalDistanceMeters());
        assertEquals(400, route.totalDurationSeconds());
        assertEquals(2, route.path().size());
    }

    @Test
    void 자동차_응답에서_거리_시간_요금_경로를_뽑는다() {
        // Directions: duration 은 밀리초, path 는 [경도, 위도]
        JsonNode root = json("""
                {"code":0,"route":{"traoptimal":[{"summary":{"distance":1747,"duration":474000,
                  "tollFare":0,"taxiFare":5800,"fuelPrice":200},
                  "path":[[127.0,37.0],[127.1,37.1]]}]}}""");

        RouteService.Leg leg = RouteService.parseDrivingLeg(root, stop("A", 1), stop("B", 2));

        assertEquals(1747, leg.response().distanceMeters());
        assertEquals(474, leg.response().durationSeconds());
        assertEquals(5800, leg.taxiFare());
        assertEquals(200, leg.fuelPrice());
        assertEquals(List.of(List.of(37.0, 127.0), List.of(37.1, 127.1)), leg.response().path());
    }

    @Test
    void 자동차_응답의_code가_0이_아니면_구간_이름이_담긴_400() {
        ResponseStatusException e = assertThrows(ResponseStatusException.class,
                () -> RouteService.parseDrivingLeg(json("{\"code\":1}"), stop("시청", 1), stop("제주공항", 2)));

        assertEquals(400, e.getStatusCode().value());
        assertEquals("'시청' → '제주공항' 사이의 자동차 경로를 찾을 수 없습니다.", e.getReason());
    }
}
