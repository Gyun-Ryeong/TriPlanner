package com.triplanner.backend.dto;

import java.util.List;

// 권역(서울 특별시/경기도 · 인천/강원도/충청도/전라도/경상도/제주도) 하나와 그 안의 도시별 날씨
public record RegionWeatherResponse(
        String regionId,
        String regionName,
        List<CityWeather> cities
) {

    public record CityWeather(
            String cityName,
            Integer temperature,
            String skyStatus,
            Integer precipitationProbability
    ) {
    }
}
