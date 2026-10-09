package com.triplanner.backend.service;

import com.triplanner.backend.common.PhoneNumbers;
import com.triplanner.backend.domain.User;
import com.triplanner.backend.dto.NotificationSettingsRequest;
import com.triplanner.backend.dto.PasswordChangeRequest;
import com.triplanner.backend.dto.ProfileResponse;
import com.triplanner.backend.dto.ProfileUpdateRequest;
import com.triplanner.backend.repository.UserRepository;
import java.nio.charset.StandardCharsets;
import org.springframework.http.HttpStatus;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;

@Service
public class ProfileService {

    private static final int BCRYPT_MAX_BYTES = 72;

    private final UserRepository userRepository;
    private final PasswordEncoder passwordEncoder;

    public ProfileService(UserRepository userRepository, PasswordEncoder passwordEncoder) {
        this.userRepository = userRepository;
        this.passwordEncoder = passwordEncoder;
    }

    @Transactional(readOnly = true)
    public ProfileResponse getProfile(String email) {
        return toResponse(findUser(email));
    }

    @Transactional
    public ProfileResponse updateProfile(String email, ProfileUpdateRequest request) {
        User user = findUser(email);
        String phone = PhoneNumbers.normalize(request.phone());
        user.changeNickname(request.nickname().trim());
        user.changePhone(phone);
        return toResponse(user);
    }

    @Transactional
    public ProfileResponse updateNotifications(String email, NotificationSettingsRequest request) {
        User user = findUser(email);
        user.changeNotifyTripAlerts(request.tripAlertsEnabled());
        return toResponse(user);
    }

    @Transactional
    public void changePassword(String email, PasswordChangeRequest request) {
        User user = findUser(email);

        if (!passwordEncoder.matches(request.currentPassword(), user.getPassword())) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "현재 비밀번호가 올바르지 않습니다.");
        }
        if (request.newPassword().getBytes(StandardCharsets.UTF_8).length > BCRYPT_MAX_BYTES) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "비밀번호가 너무 깁니다. 더 짧게 입력해 주세요.");
        }
        if (request.currentPassword().equals(request.newPassword())) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "새 비밀번호가 현재 비밀번호와 같습니다.");
        }

        user.changePassword(passwordEncoder.encode(request.newPassword()));
    }

    private User findUser(String email) {
        return userRepository.findByEmail(email)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.UNAUTHORIZED, "사용자를 찾을 수 없습니다."));
    }

    private ProfileResponse toResponse(User user) {
        return new ProfileResponse(user.getUserId(), user.getEmail(), user.getNickname(), user.getPhone(), user.isNotifyTripAlerts());
    }
}
