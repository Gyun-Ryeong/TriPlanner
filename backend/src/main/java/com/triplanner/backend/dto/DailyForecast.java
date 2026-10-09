package com.triplanner.backend.dto;

import java.time.LocalDate;

// 단기예보를 하루 단위로 요약한 값 (여행 알림 계산용)
public record DailyForecast(
        LocalDate date,
        Integer minTemp,
        Integer maxTemp,
        Integer maxPop,
        boolean rain,
        boolean snow,
        double maxHourlyRainMm,
        double maxHourlySnowCm
) {
}
