package com.triplanner.backend.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import java.time.LocalTime;

public record TripItemRequest(
        Long placeId,
        @NotBlank String itemType,
        @NotNull Integer visitOrder,
        LocalTime startTime,
        String memo
) {
}
