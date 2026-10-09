package com.triplanner.backend.security;

import java.util.List;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.security.core.Authentication;
import org.springframework.stereotype.Component;

// 관리자 계정은 DB 가 아니라 설정(admin.emails)으로 정한다. 로그인 아이디(이메일 칸 값)로 비교한다.
@Component
public class AdminAccounts {

    public static final String ROLE_ADMIN = "ROLE_ADMIN";

    private final List<String> adminEmails;

    public AdminAccounts(@Value("${admin.emails}") List<String> adminEmails) {
        this.adminEmails = adminEmails.stream().map(String::trim).filter(email -> !email.isEmpty()).toList();
    }

    public boolean isAdmin(String email) {
        return email != null && adminEmails.contains(email);
    }

    public static boolean isAdmin(Authentication authentication) {
        return authentication != null && authentication.getAuthorities().stream()
                .anyMatch(authority -> ROLE_ADMIN.equals(authority.getAuthority()));
    }
}
