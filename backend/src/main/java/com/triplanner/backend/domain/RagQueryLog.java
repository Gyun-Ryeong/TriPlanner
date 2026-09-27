package com.triplanner.backend.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.FetchType;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.Table;
import java.time.LocalDateTime;
import lombok.AccessLevel;
import lombok.Getter;
import lombok.NoArgsConstructor;

@Entity
@Table(name = "rag_query_log")
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class RagQueryLog {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "log_id")
    private Long logId;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "user_id", nullable = false)
    private User user;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "trip_id", nullable = false)
    private Trip trip;

    @Column(name = "query_text", columnDefinition = "TEXT")
    private String queryText;

    @Column(name = "response_text", columnDefinition = "TEXT")
    private String responseText;

    @Column(name = "retrieved_doc_count")
    private Integer retrievedDocCount;

    @Column(name = "response_time_ms")
    private Integer responseTimeMs;

    @Column(name = "token_used")
    private Integer tokenUsed;

    @Column(name = "created_at")
    private LocalDateTime createdAt;

    public RagQueryLog(
            User user,
            Trip trip,
            String queryText,
            String responseText,
            Integer retrievedDocCount,
            Integer responseTimeMs,
            Integer tokenUsed
    ) {
        this.user = user;
        this.trip = trip;
        this.queryText = queryText;
        this.responseText = responseText;
        this.retrievedDocCount = retrievedDocCount;
        this.responseTimeMs = responseTimeMs;
        this.tokenUsed = tokenUsed;
        this.createdAt = LocalDateTime.now();
    }
}
