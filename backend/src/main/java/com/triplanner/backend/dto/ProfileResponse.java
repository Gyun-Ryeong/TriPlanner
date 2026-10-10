package com.triplanner.backend.dto;

public record ProfileResponse(Long userId, String email, String nickname, String phone, boolean tripAlertsEnabled, boolean marketingConsent) {
}
