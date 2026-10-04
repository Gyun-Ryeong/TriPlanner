package com.triplanner.backend.dto;

import java.util.List;

public record RouteResponse(
        int totalDistanceMeters,
        int totalDurationSeconds,
        int tollFare,
        int taxiFare,
        int fuelPrice,
        List<List<Double>> path,
        List<RouteLegResponse> legs
) {
}
