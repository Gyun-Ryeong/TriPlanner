package com.triplanner.backend.dto;

import jakarta.validation.constraints.NotBlank;

public record WithdrawalRequest(
        @NotBlank(message = "비밀번호를 입력해 주세요.") String password,
        @NotBlank(message = "확인 문구를 입력해 주세요.") String confirmText
) {
}
