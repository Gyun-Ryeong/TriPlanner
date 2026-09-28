package com.triplanner.backend.dto;

public record RegionWeatherResponse(
        String regionId,
        String regionName,
        Integer temperature,
        String skyStatus,
        Integer precipitationProbability
) {
}
