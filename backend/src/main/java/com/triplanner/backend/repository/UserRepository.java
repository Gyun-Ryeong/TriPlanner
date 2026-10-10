package com.triplanner.backend.repository;

import com.triplanner.backend.domain.User;
import java.time.LocalDateTime;
import java.util.List;
import java.util.Optional;
import org.springframework.data.jpa.repository.JpaRepository;

public interface UserRepository extends JpaRepository<User, Long> {

    Optional<User> findByEmail(String email);

    boolean existsByEmail(String email);

    // JWT 인증용: 탈퇴하지 않은 회원인지
    boolean existsByEmailAndWithdrawnAtIsNull(String email);

    // 파기 대상: 탈퇴 시각이 기준 시각보다 이전인 회원
    List<User> findByWithdrawnAtBefore(LocalDateTime cutoff);
}
