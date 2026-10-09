package com.triplanner.backend.dto;

import java.time.LocalDateTime;

// 관리자 페이지 회원 목록 한 줄. 비밀번호는 절대 포함하지 않는다
public record AdminUserResponse(
        Long userId,
        String email,
        String nickname,
        String phone,
        LocalDateTime createdAt,
        boolean tripAlertsEnabled,
        boolean marketingConsent,
        long tripCount,
        boolean admin
) {
}
