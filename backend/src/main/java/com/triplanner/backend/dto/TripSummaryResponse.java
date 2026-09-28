package com.triplanner.backend.dto;

import java.time.LocalDate;

public record TripSummaryResponse(
        Long tripId,
        String title,
        String region,
        LocalDate startDate,
        LocalDate endDate,
        String status
) {
}
