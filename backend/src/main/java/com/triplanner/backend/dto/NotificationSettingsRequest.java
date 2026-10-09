package com.triplanner.backend.dto;

import jakarta.validation.constraints.NotNull;

public record NotificationSettingsRequest(@NotNull(message = "알림 설정 값이 필요합니다.") Boolean tripAlertsEnabled) {
}
