package com.triplanner.backend.dto;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;

@JsonIgnoreProperties(ignoreUnknown = true)
public record NaverProfileData(
        String id,
        String email,
        String nickname
) {
}
