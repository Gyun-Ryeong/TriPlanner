package com.triplanner.backend.service;

import com.triplanner.backend.domain.User;
import com.triplanner.backend.dto.AdminUserResponse;
import com.triplanner.backend.repository.TripRepository;
import com.triplanner.backend.repository.UserRepository;
import com.triplanner.backend.security.AdminAccounts;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import org.springframework.data.domain.Sort;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class AdminService {

    private final UserRepository userRepository;
    private final TripRepository tripRepository;
    private final AdminAccounts adminAccounts;

    public AdminService(UserRepository userRepository, TripRepository tripRepository, AdminAccounts adminAccounts) {
        this.userRepository = userRepository;
        this.tripRepository = tripRepository;
        this.adminAccounts = adminAccounts;
    }

    // 최근 가입한 회원부터
    @Transactional(readOnly = true)
    public List<AdminUserResponse> listUsers() {
        Map<Long, Long> tripCounts = new HashMap<>();
        for (Object[] row : tripRepository.countTripsByUser()) {
            tripCounts.put((Long) row[0], (Long) row[1]);
        }

        return userRepository.findAll(Sort.by(Sort.Direction.DESC, "userId")).stream()
                .map(user -> toResponse(user, tripCounts.getOrDefault(user.getUserId(), 0L)))
                .toList();
    }

    private AdminUserResponse toResponse(User user, long tripCount) {
        return new AdminUserResponse(
                user.getUserId(),
                user.getEmail(),
                user.getNickname(),
                user.getPhone(),
                user.getCreatedAt(),
                user.isNotifyTripAlerts(),
                user.isConsentMarketing(),
                tripCount,
                adminAccounts.isAdmin(user.getEmail()),
                user.getWithdrawnAt(),
                user.isWithdrawn() ? user.getWithdrawnAt().plusDays(WithdrawalService.RETENTION_DAYS) : null
        );
    }
}
