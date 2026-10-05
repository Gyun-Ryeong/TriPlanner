package com.triplanner.backend.service;

import com.triplanner.backend.common.PhoneNumbers;
import com.triplanner.backend.domain.User;
import com.triplanner.backend.dto.AuthResponse;
import com.triplanner.backend.dto.LoginRequest;
import com.triplanner.backend.dto.SignupRequest;
import com.triplanner.backend.repository.UserRepository;
import com.triplanner.backend.security.JwtProvider;
import org.springframework.http.HttpStatus;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;

@Service
public class AuthService {

    private final UserRepository userRepository;
    private final PasswordEncoder passwordEncoder;
    private final JwtProvider jwtProvider;

    public AuthService(UserRepository userRepository, PasswordEncoder passwordEncoder, JwtProvider jwtProvider) {
        this.userRepository = userRepository;
        this.passwordEncoder = passwordEncoder;
        this.jwtProvider = jwtProvider;
    }

    public AuthResponse signup(SignupRequest request) {
        if (userRepository.existsByEmail(request.email())) {
            throw new ResponseStatusException(HttpStatus.CONFLICT, "이미 가입된 이메일입니다.");
        }

        String phone = PhoneNumbers.normalize(request.phone());
        User user = new User(request.email(), passwordEncoder.encode(request.password()), request.nickname().trim());
        user.changePhone(phone);
        User saved = userRepository.save(user);

        String token = jwtProvider.generateToken(saved.getUserId(), saved.getEmail());
        return new AuthResponse(token, saved.getUserId(), saved.getEmail(), saved.getNickname());
    }

    public AuthResponse login(LoginRequest request) {
        User user = userRepository.findByEmail(request.email())
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.UNAUTHORIZED, "이메일 또는 비밀번호가 올바르지 않습니다."));

        if (!passwordEncoder.matches(request.password(), user.getPassword())) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "이메일 또는 비밀번호가 올바르지 않습니다.");
        }

        String token = jwtProvider.generateToken(user.getUserId(), user.getEmail());
        return new AuthResponse(token, user.getUserId(), user.getEmail(), user.getNickname());
    }
}
