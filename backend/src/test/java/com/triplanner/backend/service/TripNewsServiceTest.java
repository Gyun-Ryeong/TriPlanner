package com.triplanner.backend.service;

import static org.junit.jupiter.api.Assertions.assertEquals;

import org.junit.jupiter.api.Test;

// 여행지 소식을 어느 지역 기준으로 가져올지 (세부 도시 → 권역 대표 도시 → 권역 이름 그대로)
class TripNewsServiceTest {

    @Test
    void cityWinsWhenChosen() {
        assertEquals("수원", TripNewsService.placeName("수원", "경기도 / 인천"));
    }

    @Test
    void regionUsesItsRepresentativeCity() {
        assertEquals(RegionCatalog.findByName("경상도").representative().name(),
                TripNewsService.placeName("", "경상도"));
        assertEquals("인천", TripNewsService.placeName(null, "경기도 / 인천"));
    }

    @Test
    void unknownRegionIsPassedThrough() {
        assertEquals("Gyeongsang", TripNewsService.placeName("", "Gyeongsang"));
    }
}
