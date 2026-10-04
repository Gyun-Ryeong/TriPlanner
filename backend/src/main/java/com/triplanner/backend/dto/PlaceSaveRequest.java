package com.triplanner.backend.dto;

import jakarta.validation.constraints.NotBlank;

public record PlaceSaveRequest(
        @NotBlank String contentId,
        @NotBlank String name,
        String category,
        String address,
        Double latitude,
        Double longitude
) {
}
