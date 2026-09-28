package com.triplanner.backend.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import java.time.LocalDate;

public record TripUpdateRequest(
        @NotBlank String title,
        @NotBlank String region,
        @NotNull LocalDate startDate,
        @NotNull LocalDate endDate,
        @NotBlank String status
) {
}
