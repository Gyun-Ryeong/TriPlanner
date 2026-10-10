package com.triplanner.backend.service;

import com.triplanner.backend.common.PhoneNumbers;
import com.triplanner.backend.domain.User;
import com.triplanner.backend.dto.AuthResponse;
import com.triplanner.backend.dto.LoginRequest;
import com.triplanner.backend.dto.SignupRequest;
import com.triplanner.backend.repository.UserRepository;
import com.triplanner.backend.security.AdminAccounts;
import com.triplanner.backend.security.JwtProvider;
import org.springframework.http.HttpStatus;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;

@Service
public class AuthService {

    // 탈퇴 보관 기간(WithdrawalService.RETENTION_DAYS) 안의 계정: 로그인과 같은 이메일 재가입을 막는다
    static final String WITHDRAWN_ACCOUNT_MESSAGE =
            "탈퇴 처리된 계정입니다. 탈퇴 후 " + WithdrawalService.RETENTION_DAYS + "일 안에는 운영팀에 문의해 복구할 수 있습니다.";
    private static final String WITHDRAWN_EMAIL_MESSAGE =
            "탈퇴 처리 중인 이메일입니다. 탈퇴 후 " + WithdrawalService.RETENTION_DAYS + "일이 지나면 다시 가입할 수 있습니다.";

    private final UserRepository userRepository;
    private final PasswordEncoder passwordEncoder;
    private final JwtProvider jwtProvider;
    private final AdminAccounts adminAccounts;

    public AuthService(
            UserRepository userRepository,
            PasswordEncoder passwordEncoder,
            JwtProvider jwtProvider,
            AdminAccounts adminAccounts
    ) {
        this.userRepository = userRepository;
        this.passwordEncoder = passwordEncoder;
        this.jwtProvider = jwtProvider;
        this.adminAccounts = adminAccounts;
    }

    public AuthResponse signup(SignupRequest request) {
        userRepository.findByEmail(request.email()).ifPresent(existing -> {
            if (existing.isWithdrawn()) {
                throw new ResponseStatusException(HttpStatus.CONFLICT, WITHDRAWN_EMAIL_MESSAGE);
            }
            throw new ResponseStatusException(HttpStatus.CONFLICT, "이미 가입된 이메일입니다.");
        });

        if (!Boolean.TRUE.equals(request.agreeTerms()) || !Boolean.TRUE.equals(request.agreePrivacy())) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "필수 약관에 동의해 주세요.");
        }

        String phone = PhoneNumbers.normalize(request.phone());
        User user = new User(request.email(), passwordEncoder.encode(request.password()), request.nickname().trim());
        user.changePhone(phone);
        user.recordSignupConsent(
                Boolean.TRUE.equals(request.agreeTripAlerts()),
                Boolean.TRUE.equals(request.agreeMarketing())
        );
        User saved = userRepository.save(user);

        String token = jwtProvider.generateToken(saved.getUserId(), saved.getEmail());
        return new AuthResponse(token, saved.getUserId(), saved.getEmail(), saved.getNickname(), adminAccounts.isAdmin(saved.getEmail()));
    }

    public AuthResponse login(LoginRequest request) {
        User user = userRepository.findByEmail(request.email())
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.UNAUTHORIZED, "이메일 또는 비밀번호가 올바르지 않습니다."));

        if (!passwordEncoder.matches(request.password(), user.getPassword())) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "이메일 또는 비밀번호가 올바르지 않습니다.");
        }
        if (user.isWithdrawn()) {
            throw new ResponseStatusException(HttpStatus.FORBIDDEN, WITHDRAWN_ACCOUNT_MESSAGE);
        }

        String token = jwtProvider.generateToken(user.getUserId(), user.getEmail());
        return new AuthResponse(token, user.getUserId(), user.getEmail(), user.getNickname(), adminAccounts.isAdmin(user.getEmail()));
    }
}
