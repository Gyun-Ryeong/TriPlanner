package com.triplanner.backend.dto;

import java.time.LocalDate;

public record TripSummaryResponse(
        Long tripId,
        String title,
        String region,
        String city,
        LocalDate startDate,
        LocalDate endDate,
        String status
) {
}
