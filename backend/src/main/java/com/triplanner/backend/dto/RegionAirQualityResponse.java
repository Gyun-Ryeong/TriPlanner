package com.triplanner.backend.dto;

import java.util.List;

// 권역 하나의 대기질. 권역 값(pm10 등)은 권역 안 시도 중 가장 나쁜(높은) 값이고, areas 에 시도별 값이 들어 있다.
public record RegionAirQualityResponse(
        String regionId,
        String regionName,
        String dataTime,
        Metric pm10,
        Metric pm25,
        Metric o3,
        Metric khai,
        List<AreaAirQuality> areas
) {

    // 시도 하나(예: 대구)의 대기질 - 시도 내 측정소 평균
    public record AreaAirQuality(
            String areaName,
            String dataTime,
            Metric pm10,
            Metric pm25,
            Metric o3,
            Metric khai
    ) {
    }

    // value: 측정소 평균(소수점 처리됨), grade: 좋음/보통/나쁨/매우나쁨 (측정값이 없으면 null),
    // area: 권역 값일 때 그 값이 나온 시도 이름 (시도가 하나뿐인 권역이거나 시도 값이면 null)
    public record Metric(Double value, String grade, String area) {
    }
}
