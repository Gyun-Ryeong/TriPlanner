package com.triplanner.backend.dto;

import java.time.LocalDate;
import java.util.List;

// 일정 변경·준비 알림. alertsEnabled: 프로필에서 켜두었는지 (false 이면 trips 는 비어 있다). trips 에는 알림이 있는 여행만 담긴다
public record PrepAlertsResponse(boolean alertsEnabled, List<TripPrepAlerts> trips) {

    public record TripPrepAlerts(
            Long tripId,
            String title,
            String region,
            LocalDate startDate,
            long daysUntilStart,
            List<PrepAlert> alerts
    ) {
    }

    // kind: CHECKLIST(체크리스트 기한) / EMPTY_DAY(비어 있는 일정), level: DANGER(기한 지남) / CAUTION(참고)
    public record PrepAlert(String level, String kind, String message) {
    }
}
