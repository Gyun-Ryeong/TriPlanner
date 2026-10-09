package com.triplanner.backend.controller;

import tools.jackson.databind.JsonNode;
import com.triplanner.backend.dto.RagChatRequest;
import com.triplanner.backend.security.AdminAccounts;
import com.triplanner.backend.service.RagChatService;
import jakarta.validation.Valid;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.DeleteMapping;
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
        boolean debug = Boolean.TRUE.equals(request.debug()) && AdminAccounts.isAdmin(authentication);
        return ResponseEntity.ok(ragChatService.chat(request.sessionId(), request.message(), debug));
    }

    @DeleteMapping("/{sessionId}")
    public ResponseEntity<Void> reset(@PathVariable String sessionId) {
        if (!sessionId.matches("^[a-f0-9]{1,32}$")) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "대화 정보가 올바르지 않습니다.");
        }
        ragChatService.reset(sessionId);
        return ResponseEntity.noContent().build();
    }
}
