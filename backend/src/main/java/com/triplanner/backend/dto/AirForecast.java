package com.triplanner.backend.dto;

import java.time.LocalDate;
import java.util.Map;

// 에어코리아 미세먼지 예보통보: 항목(PM10/PM25) -> 날짜 -> 권역 -> 등급(좋음/보통/나쁨/매우나쁨)
public record AirForecast(Map<String, Map<LocalDate, Map<String, String>>> grades) {

    public String grade(String informCode, LocalDate date, String area) {
        Map<LocalDate, Map<String, String>> byDate = grades.get(informCode);
        if (byDate == null) {
            return null;
        }
        Map<String, String> byArea = byDate.get(date);
        return byArea == null ? null : byArea.get(area);
    }
}
