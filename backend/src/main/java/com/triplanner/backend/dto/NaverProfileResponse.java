package com.triplanner.backend.dto;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;

@JsonIgnoreProperties(ignoreUnknown = true)
public record NaverProfileResponse(
        String resultcode,
        String message,
        NaverProfileData response
) {
}
