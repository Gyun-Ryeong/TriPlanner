package com.triplanner.backend.service;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.triplanner.backend.service.ChecklistService.Draft;
import java.time.LocalDate;
import java.util.List;
import org.junit.jupiter.api.Test;

class ChecklistServiceTest {

    private static boolean has(List<Draft> items, String keyword) {
        return items.stream().anyMatch(item -> item.content().contains(keyword));
    }

    @Test
    void dayTripSkipsLodgingAndOvernightItems() {
        List<Draft> items = ChecklistService.defaultItems("서울 특별시", LocalDate.of(2026, 10, 20), LocalDate.of(2026, 10, 20));

        assertFalse(has(items, "숙소"));
        assertFalse(has(items, "세면도구"));
        assertFalse(has(items, "문단속"));
        assertTrue(has(items, "교통편 예약"));
    }

    @Test
    void overnightTripAddsLodgingAndPackingItems() {
        List<Draft> items = ChecklistService.defaultItems("강원도", LocalDate.of(2026, 10, 20), LocalDate.of(2026, 10, 22));

        assertTrue(has(items, "숙소"));
        assertTrue(has(items, "세면도구"));
        assertTrue(has(items, "문단속"));
    }

    @Test
    void jejuTripNeedsFlightAndRentalCar() {
        List<Draft> items = ChecklistService.defaultItems("제주도", LocalDate.of(2026, 10, 20), LocalDate.of(2026, 10, 22));

        assertTrue(has(items, "항공권·렌터카"));
        assertTrue(has(items, "항공편 결항"));
        assertFalse(has(items, "KTX"));
    }

    @Test
    void seasonDecidesClothingItem() {
        assertTrue(has(ChecklistService.defaultItems("서울 특별시", LocalDate.of(2026, 7, 10), LocalDate.of(2026, 7, 11)), "자외선"));
        assertTrue(has(ChecklistService.defaultItems("서울 특별시", LocalDate.of(2026, 7, 10), LocalDate.of(2026, 7, 11)), "우산"));
        assertTrue(has(ChecklistService.defaultItems("서울 특별시", LocalDate.of(2027, 1, 10), LocalDate.of(2027, 1, 11)), "방한"));
        assertTrue(has(ChecklistService.defaultItems("서울 특별시", LocalDate.of(2026, 10, 10), LocalDate.of(2026, 10, 11)), "겉옷"));
        assertFalse(has(ChecklistService.defaultItems("서울 특별시", LocalDate.of(2026, 10, 10), LocalDate.of(2026, 10, 11)), "우산"));
    }

    private static List<Integer> offsets(List<Draft> items) {
        return items.stream().map(Draft::dueOffsetDays).distinct().sorted().toList();
    }

    @Test
    void itemsWhoseDeadlineAlreadyPassedAreNotCreated() {
        LocalDate today = LocalDate.of(2026, 10, 13);
        LocalDate end = LocalDate.of(2026, 10, 25);
        List<Draft> all = ChecklistService.defaultItems("강원도", LocalDate.of(2026, 10, 20), end);

        // 출발 7일 뒤: D-7 기한이 오늘이라 전부 남는다
        assertEquals(List.of(0, 1, 3, 7), offsets(ChecklistService.withoutAlreadyPastDue(all, LocalDate.of(2026, 10, 20), today)));
        // 5일 뒤: D-7(기한 2일 전)은 빠진다
        assertEquals(List.of(0, 1, 3), offsets(ChecklistService.withoutAlreadyPastDue(all, LocalDate.of(2026, 10, 18), today)));
        // 2일 뒤: D-7, D-3 이 빠지고 D-1, 당일만 남는다
        assertEquals(List.of(0, 1), offsets(ChecklistService.withoutAlreadyPastDue(all, LocalDate.of(2026, 10, 15), today)));
        // 오늘 출발: 당일 항목만 남는다
        assertEquals(List.of(0), offsets(ChecklistService.withoutAlreadyPastDue(all, today, today)));
    }

    @Test
    void everyItemHasKnownDeadline() {
        List<Draft> items = ChecklistService.defaultItems("경상도", LocalDate.of(2026, 5, 1), LocalDate.of(2026, 5, 3));

        assertTrue(items.stream().allMatch(item -> List.of(0, 1, 3, 7).contains(item.dueOffsetDays())));
        assertEquals(items.size(), items.stream().map(Draft::content).distinct().count());
    }
}
