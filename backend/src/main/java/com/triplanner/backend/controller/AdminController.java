package com.triplanner.backend.controller;

import com.triplanner.backend.dto.AdminUserResponse;
import com.triplanner.backend.service.AdminService;
import com.triplanner.backend.service.RagChatService;
import com.triplanner.backend.service.WithdrawalService;
import java.util.List;
import java.util.Map;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

// /api/admin/** 는 SecurityConfig 에서 관리자(ROLE_ADMIN)만 접근하도록 막는다
@RestController
@RequestMapping("/api/admin")
public class AdminController {

    private final RagChatService ragChatService;
    private final AdminService adminService;
    private final WithdrawalService withdrawalService;

    public AdminController(RagChatService ragChatService, AdminService adminService, WithdrawalService withdrawalService) {
        this.ragChatService = ragChatService;
        this.adminService = adminService;
        this.withdrawalService = withdrawalService;
    }

    @GetMapping("/status")
    public ResponseEntity<Map<String, Object>> status() {
        return ResponseEntity.ok(Map.of("chatbotServerUp", ragChatService.isServerUp()));
    }

    @GetMapping("/users")
    public ResponseEntity<List<AdminUserResponse>> users() {
        return ResponseEntity.ok(adminService.listUsers());
    }

    // 탈퇴 회원 복구 (보관 기간 안에만 가능, 기간이 지나면 이미 파기되어 있다)
    @PostMapping("/users/{userId}/restore")
    public ResponseEntity<Void> restoreUser(@PathVariable Long userId) {
        withdrawalService.restore(userId);
        return ResponseEntity.noContent().build();
    }
}
