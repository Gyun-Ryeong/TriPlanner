package com.triplanner.backend.dto;

import java.time.LocalDate;
import java.util.List;

// alertsEnabled: 사용자가 프로필에서 여행 알림을 켜두었는지 (false 이면 trips 는 비어 있다)
public record TripAlertsResponse(boolean alertsEnabled, List<TripAlerts> trips, List<String> unavailableSources) {

    // forecastAvailable: 여행 시작이 예보 제공 범위(오늘 포함 3일) 안에 들어왔는지
    public record TripAlerts(
            Long tripId,
            String title,
            String region,
            LocalDate startDate,
            LocalDate endDate,
            long daysUntilStart,
            boolean forecastAvailable,
            List<Alert> alerts
    ) {
    }

    // level: DANGER(강한 단계) / CAUTION(약한 단계), kind: PRECIPITATION / TEMPERATURE / AIR / WARNING, date: 특보는 null
    public record Alert(String level, String kind, LocalDate date, String message) {
    }
}
