package com.triplanner.backend.dto;

import jakarta.validation.constraints.NotNull;

public record MarketingConsentRequest(@NotNull(message = "마케팅 수신 동의 값이 필요합니다.") Boolean marketingConsent) {
}
