package com.triplanner.backend.service;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.Test;
import org.springframework.web.server.ResponseStatusException;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.json.JsonMapper;

class HolidayServiceTest {

    private final TourApiClient parser = new TourApiClient(JsonMapper.builder().build(), "test-key");
    private final HolidayService service = new HolidayService(parser, "test-key");

    @Test
    void 쉬는_날만_날짜_형식을_바꿔_담고_같은_날_이름은_이어_붙인다() {
        List<JsonNode> items = parser.parseItems("getRestDeInfo", """
                {"response":{"header":{"resultCode":"00","resultMsg":"NORMAL SERVICE."},
                 "body":{"items":{"item":[
                   {"dateName":"어린이날","isHoliday":"Y","locdate":20260505},
                   {"dateName":"부처님오신날","isHoliday":"Y","locdate":20260505},
                   {"dateName":"기념일","isHoliday":"N","locdate":20260510}]}}}}""");

        Map<String, String> days = HolidayService.toDays(items);

        assertEquals(Map.of("2026-05-05", "어린이날 · 부처님오신날"), days);
    }

    @Test
    void 항목이_하나만_와도_읽는다() {
        List<JsonNode> items = parser.parseItems("getRestDeInfo", """
                {"response":{"header":{"resultCode":"00"},
                 "body":{"items":{"item":{"dateName":"성탄절","isHoliday":"Y","locdate":20261225}}}}}""");

        assertEquals(Map.of("2026-12-25", "성탄절"), HolidayService.toDays(items));
    }

    @Test
    void 휴일이_없는_달은_빈_목록() {
        List<JsonNode> items = parser.parseItems("getRestDeInfo", """
                {"response":{"header":{"resultCode":"00"},"body":{"items":"","totalCount":0}}}""");

        assertTrue(HolidayService.toDays(items).isEmpty());
    }

    @Test
    void 범위를_벗어난_연월은_400() {
        assertEquals(400, assertThrows(ResponseStatusException.class, () -> service.getMonth(2026, 13))
                .getStatusCode().value());
        assertEquals(400, assertThrows(ResponseStatusException.class, () -> service.getMonth(1999, 1))
                .getStatusCode().value());
    }
}
