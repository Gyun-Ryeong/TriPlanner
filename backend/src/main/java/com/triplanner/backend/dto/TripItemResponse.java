package com.triplanner.backend.dto;

import java.time.LocalTime;

public record TripItemResponse(
        Long tripItemId,
        Long placeId,
        String placeContentId,
        String placeName,
        Double placeLatitude,
        Double placeLongitude,
        String itemType,
        Integer visitOrder,
        LocalTime startTime,
        String memo
) {
}
