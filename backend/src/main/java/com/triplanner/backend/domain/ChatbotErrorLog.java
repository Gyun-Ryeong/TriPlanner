package com.triplanner.backend.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import java.time.LocalDateTime;

// 챗봇(RAG 서버) 호출이 실패한 기록. 관리자 페이지에서 보며, 회원 FK 를 두지 않아 회원·여행과 상관없이 쌓고 지울 수 있다
@Entity
@Table(name = "chatbot_error_log")
public class ChatbotErrorLog {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "error_id")
    private Long errorId;

    @Column(name = "user_id")
    private Long userId;

    // CONNECTION / TIMEOUT / AI_MODEL / SERVER_ERROR / BAD_REQUEST / OTHER (화면에 보이는 이름은 프론트에서 정한다)
    @Column(name = "category", nullable = false, length = 20)
    private String category;

    // RAG 서버가 응답한 HTTP 상태. 서버에 닿지 못한 경우는 NULL
    @Column(name = "http_status")
    private Integer httpStatus;

    // RAG 서버가 알려준 원인 또는 예외 메시지 (최대 500자)
    @Column(name = "detail", length = 500)
    private String detail;

    // 사용자가 보낸 질문의 앞부분 (최대 100자). 인사말 요청처럼 질문이 없으면 NULL
    @Column(name = "query_preview", length = 100)
    private String queryPreview;

    @Column(name = "created_at", nullable = false)
    private LocalDateTime createdAt;

    protected ChatbotErrorLog() {
    }

    public ChatbotErrorLog(Long userId, String category, Integer httpStatus, String detail, String queryPreview) {
        this.userId = userId;
        this.category = category;
        this.httpStatus = httpStatus;
        this.detail = detail;
        this.queryPreview = queryPreview;
        this.createdAt = LocalDateTime.now();
    }

    public Long getErrorId() {
        return errorId;
    }

    public Long getUserId() {
        return userId;
    }

    public String getCategory() {
        return category;
    }

    public Integer getHttpStatus() {
        return httpStatus;
    }

    public String getDetail() {
        return detail;
    }

    public String getQueryPreview() {
        return queryPreview;
    }

    public LocalDateTime getCreatedAt() {
        return createdAt;
    }
}
