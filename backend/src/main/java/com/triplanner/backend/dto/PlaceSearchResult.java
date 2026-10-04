package com.triplanner.backend.dto;

public record PlaceSearchResult(
        String contentId,
        String name,
        String category,
        String address,
        Double latitude,
        Double longitude,
        String imageUrl
) {
}
