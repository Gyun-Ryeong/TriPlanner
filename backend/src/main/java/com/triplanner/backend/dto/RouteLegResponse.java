package com.triplanner.backend.dto;

import java.util.List;

public record RouteLegResponse(
        Long fromItemId,
        Long toItemId,
        int distanceMeters,
        int durationSeconds,
        List<List<Double>> path
) {
}
