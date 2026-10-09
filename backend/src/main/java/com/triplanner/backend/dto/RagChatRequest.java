package com.triplanner.backend.dto;

import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;

// sessionId 가 비어 있으면 RAG 서버가 새 대화를 시작하고, message 가 비어 있으면 인사말을 돌려준다
public record RagChatRequest(
        @Pattern(regexp = "^[a-f0-9]{1,32}$", message = "대화 정보가 올바르지 않습니다.")
        String sessionId,

        @Size(max = 1000, message = "메시지는 1000자 이하로 입력해 주세요.")
        String message,

        // 챗봇 개발자 모드 (API 오류·소요 시간 포함). 관리자가 아니면 무시된다
        Boolean debug
) {
}
