package com.triplanner.backend.dto;

public record AuthResponse(
        String token,
        Long userId,
        String email,
        String nickname
) {
}
