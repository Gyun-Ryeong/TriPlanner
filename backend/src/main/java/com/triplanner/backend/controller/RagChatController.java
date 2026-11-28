package com.triplanner.backend.controller;

import tools.jackson.databind.JsonNode;
import com.triplanner.backend.dto.RagChatRequest;
import com.triplanner.backend.service.RagChatService;
import jakarta.validation.Valid;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

@RestController
@RequestMapping("/api/chat")
public class RagChatController {

    private final RagChatService ragChatService;

    public RagChatController(RagChatService ragChatService) {
        this.ragChatService = ragChatService;
    }

    // 응답은 RAG 서버(/chat)의 JSON 을 그대로 돌려준다 (session_id, reply, stage, plan ...)
    @PostMapping
    public ResponseEntity<JsonNode> chat(@Valid @RequestBody RagChatRequest request, Authentication authentication) {
        return ResponseEntity.ok(ragChatService.chat(authentication.getName(), request.sessionId(), request.message()));
    }

    // 방금 보낸 말을 취소한다 (챗봇이 그 말로 바꿔 둔 조건·일정을 보내기 전으로 되돌림)
    @PostMapping("/{sessionId}/cancel")
    public ResponseEntity<Void> cancel(@PathVariable String sessionId) {
        validateSessionId(sessionId);
        ragChatService.cancel(sessionId);
        return ResponseEntity.noContent().build();
    }

    // 답을 기다리는 동안 챗봇이 지금 하는 일 (busy, step, elapsed). 화면이 1~2초마다 묻는다
    @GetMapping("/{sessionId}/progress")
    public ResponseEntity<JsonNode> progress(@PathVariable String sessionId) {
        validateSessionId(sessionId);
        return ResponseEntity.ok(ragChatService.progress(sessionId));
    }

    @DeleteMapping("/{sessionId}")
    public ResponseEntity<Void> reset(@PathVariable String sessionId) {
        validateSessionId(sessionId);
        ragChatService.reset(sessionId);
        return ResponseEntity.noContent().build();
    }

    private static void validateSessionId(String sessionId) {
        if (!sessionId.matches("^[a-f0-9]{1,32}$")) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "대화 정보가 올바르지 않습니다.");
        }
    }
}
