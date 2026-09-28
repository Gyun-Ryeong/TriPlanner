package com.triplanner.backend.dto;

import java.time.LocalDate;
import java.util.List;

public record TripDayResponse(
        Long tripDayId,
        Integer dayNumber,
        LocalDate date,
        List<TripItemResponse> items
) {
}
