package com.triplanner.backend.dto;

// 바꾸려는 설정만 보낸다 (null 인 항목은 그대로 둔다). 둘 다 비어 있으면 요청을 거절한다
public record NotificationSettingsRequest(Boolean tripAlertsEnabled, Boolean scheduleAlertsEnabled) {
}
