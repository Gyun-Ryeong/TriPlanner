package com.triplanner.backend.dto;

import java.time.LocalDate;
import java.util.List;

public record TripDetailResponse(
        Long tripId,
        String title,
        String region,
        String city,
        LocalDate startDate,
        LocalDate endDate,
        String status,
        // 공유 링크의 비밀 코드 (공유하지 않으면 null). 여행 주인에게만 내려가는 응답이다
        String shareCode,
        List<TripDayResponse> days
) {
}
