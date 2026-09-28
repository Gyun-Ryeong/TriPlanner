package com.triplanner.backend.dto;

import java.time.LocalDate;
import java.util.List;

public record TripDetailResponse(
        Long tripId,
        String title,
        String region,
        LocalDate startDate,
        LocalDate endDate,
        String status,
        List<TripDayResponse> days
) {
}
