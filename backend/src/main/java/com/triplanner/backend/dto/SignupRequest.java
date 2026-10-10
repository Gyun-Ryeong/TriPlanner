package com.triplanner.backend.dto;

import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

// agreeTerms / agreePrivacy 는 필수 약관(true 여야 가입 가능), 나머지 두 개는 선택 동의(없으면 false)
public record SignupRequest(
        @NotBlank @Email String email,
        @NotBlank @Size(min = 8, message = "비밀번호는 8자 이상이어야 합니다.") String password,
        @NotBlank @Size(max = 50, message = "이름은 50자 이하여야 합니다.") String nickname,
        @Size(max = 20, message = "전화번호가 너무 깁니다.") String phone,
        Boolean agreeTerms,
        Boolean agreePrivacy,
        Boolean agreeTripAlerts,
        Boolean agreeMarketing
) {
}
