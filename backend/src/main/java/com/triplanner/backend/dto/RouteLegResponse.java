package com.triplanner.backend.dto;

import java.util.List;

// available=false 는 경로를 만들 수 없는 구간(도보로 너무 먼 거리 등)이다. 이때 거리·시간은 0, path 는 비어 있다.
public record RouteLegResponse(
        Long fromItemId,
        Long toItemId,
        int distanceMeters,
        int durationSeconds,
        List<List<Double>> path,
        boolean available
) {
}
