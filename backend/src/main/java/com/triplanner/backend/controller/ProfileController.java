package com.triplanner.backend.controller;

import com.triplanner.backend.dto.MarketingConsentRequest;
import com.triplanner.backend.dto.NotificationSettingsRequest;
import com.triplanner.backend.dto.PasswordChangeRequest;
import com.triplanner.backend.dto.ProfileResponse;
import com.triplanner.backend.dto.ProfileUpdateRequest;
import com.triplanner.backend.dto.WithdrawalRequest;
import com.triplanner.backend.service.ProfileService;
import com.triplanner.backend.service.WithdrawalService;
import jakarta.validation.Valid;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/me")
public class ProfileController {

    private final ProfileService profileService;
    private final WithdrawalService withdrawalService;

    public ProfileController(ProfileService profileService, WithdrawalService withdrawalService) {
        this.profileService = profileService;
        this.withdrawalService = withdrawalService;
    }

    @GetMapping
    public ResponseEntity<ProfileResponse> getProfile(Authentication authentication) {
        return ResponseEntity.ok(profileService.getProfile(authentication.getName()));
    }

    @PutMapping
    public ResponseEntity<ProfileResponse> updateProfile(
            Authentication authentication,
            @Valid @RequestBody ProfileUpdateRequest request
    ) {
        return ResponseEntity.ok(profileService.updateProfile(authentication.getName(), request));
    }

    @PutMapping("/notifications")
    public ResponseEntity<ProfileResponse> updateNotifications(
            Authentication authentication,
            @Valid @RequestBody NotificationSettingsRequest request
    ) {
        return ResponseEntity.ok(profileService.updateNotifications(authentication.getName(), request));
    }

    @PutMapping("/marketing")
    public ResponseEntity<ProfileResponse> updateMarketingConsent(
            Authentication authentication,
            @Valid @RequestBody MarketingConsentRequest request
    ) {
        return ResponseEntity.ok(profileService.updateMarketingConsent(authentication.getName(), request));
    }

    @PutMapping("/password")
    public ResponseEntity<Void> changePassword(
            Authentication authentication,
            @Valid @RequestBody PasswordChangeRequest request
    ) {
        profileService.changePassword(authentication.getName(), request);
        return ResponseEntity.noContent().build();
    }

    // 회원 탈퇴: 비밀번호와 확인 문구('회원탈퇴')가 맞아야 한다.
    // (네이버 가입 회원은 비밀번호를 알 수 없어 지금은 탈퇴할 수 없다 - 소셜 로그인 구현 때 다시 정한다)
    @PostMapping("/withdrawal")
    public ResponseEntity<Void> withdraw(
            Authentication authentication,
            @Valid @RequestBody WithdrawalRequest request
    ) {
        withdrawalService.withdraw(authentication.getName(), request);
        return ResponseEntity.noContent().build();
    }
}
