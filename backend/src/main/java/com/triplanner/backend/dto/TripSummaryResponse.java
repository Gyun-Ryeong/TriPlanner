package com.triplanner.backend.dto;

import java.time.LocalDate;

public record TripSummaryResponse(
        Long tripId,
        String title,
        String region,
        String city,
        LocalDate startDate,
        LocalDate endDate,
        String status,
        // 공유 중이면 공유 링크 코드, 아니면 null (여행 목록에서 '공유 중' 표시에 쓴다)
        String shareCode
) {
}
