package com.triplanner.backend.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import java.time.LocalDateTime;
import lombok.AccessLevel;
import lombok.Getter;
import lombok.NoArgsConstructor;

@Entity
@Table(name = "`user`")
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class User {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "user_id")
    private Long userId;

    @Column(name = "email", unique = true)
    private String email;

    @Column(name = "password")
    private String password;

    @Column(name = "nickname")
    private String nickname;

    @Column(name = "phone")
    private String phone;

    @Column(name = "created_at")
    private LocalDateTime createdAt;

    // 여행 위험 실시간 알림 수신 여부 (프로필에서 켜고 끈다, 회원가입 시 '여행 알림 수신 동의'로 처음 값이 정해진다)
    @Column(name = "notify_trip_alerts", nullable = false)
    private boolean notifyTripAlerts = true;

    // 회원가입 때 필수 약관(이용약관, 개인정보 수집·이용)에 동의한 시각 (회원가입 폼을 거치지 않은 계정은 null)
    @Column(name = "consent_at")
    private LocalDateTime consentAt;

    // 제3자 제공 동의 항목은 회원가입에서 삭제됨 (제3자 제공을 하지 않음). 기존 DB 컬럼 호환을 위해 남겨 두며 새 가입자는 항상 false
    @Column(name = "consent_third_party", nullable = false)
    private boolean consentThirdParty;

    @Column(name = "consent_marketing", nullable = false)
    private boolean consentMarketing;

    // 회원 탈퇴 시각. null 이면 정상 회원이고, 값이 있으면 로그인·API 사용이 막히며 보관 기간이 지나면 관련 데이터와 함께 파기된다
    @Column(name = "withdrawn_at")
    private LocalDateTime withdrawnAt;

    public User(String email, String password, String nickname) {
        this.email = email;
        this.password = password;
        this.nickname = nickname;
        this.createdAt = LocalDateTime.now();
    }

    public void changeNickname(String nickname) {
        this.nickname = nickname;
    }

    public void changePhone(String phone) {
        this.phone = phone;
    }

    public void changePassword(String encodedPassword) {
        this.password = encodedPassword;
    }

    public void changeNotifyTripAlerts(boolean enabled) {
        this.notifyTripAlerts = enabled;
    }

    public void changeConsentMarketing(boolean consent) {
        this.consentMarketing = consent;
    }

    public void recordSignupConsent(boolean tripAlerts, boolean marketing) {
        this.consentAt = LocalDateTime.now();
        this.notifyTripAlerts = tripAlerts;
        this.consentMarketing = marketing;
    }

    public void withdraw() {
        this.withdrawnAt = LocalDateTime.now();
    }

    public void restore() {
        this.withdrawnAt = null;
    }

    public boolean isWithdrawn() {
        return withdrawnAt != null;
    }
}
