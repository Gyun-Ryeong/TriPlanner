package com.triplanner.backend.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;
import java.time.LocalDate;

public record TripUpdateRequest(
        @NotBlank String title,
        @NotBlank String region,
        @Size(max = 30) String city,
        @NotNull LocalDate startDate,
        @NotNull LocalDate endDate,
        @NotBlank String status
) {
}
