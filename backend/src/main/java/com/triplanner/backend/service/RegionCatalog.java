package com.triplanner.backend.service;

import java.util.List;

// 앱의 7개 광역 권역(이름은 여행 만들기 화면과 동일)과 그 아래 주요 도시 목록.
// 날씨 조회(기상청 단기예보 격자 좌표)와 여행 만들기의 '세부 지역' 선택이 같은 목록을 쓴다.
public final class RegionCatalog {

    public record CityGrid(String name, int nx, int ny) {
    }

    // cities 의 첫 번째 도시가 대표 도시다 (세부 지역을 고르지 않은 여행의 예보는 대표 도시 기준)
    public record RegionGrid(String id, String name, List<CityGrid> cities) {
        public CityGrid representative() {
            return cities.get(0);
        }

        public CityGrid cityByName(String cityName) {
            return cities.stream().filter(c -> c.name().equals(cityName)).findFirst().orElse(null);
        }
    }

    // 격자는 기상청 공식 변환식으로 계산했다 (기존 검증된 대표 도시 6곳과 일치 확인, 오차는 격자 1칸=5km 이내).
    public static final List<RegionGrid> REGIONS = List.of(
            new RegionGrid("seoul", "서울 특별시", List.of(
                    new CityGrid("서울", 60, 127))),
            new RegionGrid("gi", "경기도 / 인천", List.of(
                    new CityGrid("인천", 55, 124),
                    new CityGrid("수원", 61, 120),
                    new CityGrid("가평", 69, 133))),
            new RegionGrid("gangwon", "강원도", List.of(
                    new CityGrid("춘천", 73, 134),
                    new CityGrid("강릉", 92, 132),
                    new CityGrid("속초", 87, 141))),
            new RegionGrid("chungcheong", "충청도", List.of(
                    new CityGrid("대전", 67, 100),
                    new CityGrid("청주", 69, 107),
                    new CityGrid("천안", 62, 110),
                    new CityGrid("태안", 48, 109))),
            new RegionGrid("jeolla", "전라도", List.of(
                    new CityGrid("광주", 58, 74),
                    new CityGrid("전주", 63, 89),
                    new CityGrid("여수", 73, 66),
                    new CityGrid("목포", 50, 67))),
            new RegionGrid("gyeongsang", "경상도", List.of(
                    new CityGrid("부산", 98, 76),
                    new CityGrid("대구", 89, 91),
                    new CityGrid("울산", 102, 84),
                    new CityGrid("경주", 100, 91),
                    new CityGrid("안동", 91, 106))),
            new RegionGrid("jeju", "제주도", List.of(
                    new CityGrid("제주", 52, 38),
                    new CityGrid("서귀포", 52, 33)))
    );

    private RegionCatalog() {
    }

    // 권역 이름(공백은 무시)으로 찾는다. 없으면 null
    public static RegionGrid findByName(String regionName) {
        String wanted = compact(regionName);
        return REGIONS.stream().filter(r -> compact(r.name()).equals(wanted)).findFirst().orElse(null);
    }

    public static RegionGrid findById(String regionId) {
        return REGIONS.stream().filter(r -> r.id().equals(regionId)).findFirst().orElse(null);
    }

    private static String compact(String text) {
        return text == null ? "" : text.replaceAll("\\s+", "");
    }
}
