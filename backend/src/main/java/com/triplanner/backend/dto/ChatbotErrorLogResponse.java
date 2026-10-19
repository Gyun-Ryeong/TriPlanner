package com.triplanner.backend.dto;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;

// 관리자 페이지 '챗봇 오류 기록'. counts 는 분류 코드별 전체 건수(보관 기간 안), items 는 선택한 분류의 최근 50건
public record ChatbotErrorLogResponse(long total, Map<String, Long> counts, List<Item> items) {

    // 회원이 이미 파기됐거나 비로그인 호출이면 userId·email·nickname 이 NULL 이다
    public record Item(
            Long errorId,
            LocalDateTime createdAt,
            Long userId,
            String email,
            String nickname,
            String category,
            Integer httpStatus,
            String detail,
            String queryPreview
    ) {
    }
}
