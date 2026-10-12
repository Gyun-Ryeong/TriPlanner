package com.triplanner.backend.dto;

import java.util.List;

// mode: DRIVING(자동차) / WALKING(도보). 도보일 때 tollFare·taxiFare·fuelPrice 는 0 이다.
public record RouteResponse(
        String mode,
        int totalDistanceMeters,
        int totalDurationSeconds,
        int tollFare,
        int taxiFare,
        int fuelPrice,
        List<List<Double>> path,
        List<RouteLegResponse> legs
) {
}
