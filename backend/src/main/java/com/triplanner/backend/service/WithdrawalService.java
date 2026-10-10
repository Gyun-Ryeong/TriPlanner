package com.triplanner.backend.service;

import com.triplanner.backend.domain.User;
import com.triplanner.backend.repository.RagQueryLogRepository;
import com.triplanner.backend.repository.TripDayRepository;
import com.triplanner.backend.repository.TripItemRepository;
import com.triplanner.backend.repository.TripRepository;
import com.triplanner.backend.repository.UserRepository;
import java.time.LocalDateTime;
import java.util.List;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatus;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;

// 회원 탈퇴: 탈퇴하면 바로 로그인·API 사용이 막히고, 보관 기간(14일)이 지나면 회원과 관련 데이터를 모두 파기한다.
// 보관 기간은 약관(약관동의.md, 개인정보 수집·이용 3항)과 맞아야 하므로 바꿀 때는 약관 문구도 함께 고친다.
@Service
public class WithdrawalService {

    public static final int RETENTION_DAYS = 14;

    private static final Logger log = LoggerFactory.getLogger(WithdrawalService.class);

    private final UserRepository userRepository;
    private final TripRepository tripRepository;
    private final TripDayRepository tripDayRepository;
    private final TripItemRepository tripItemRepository;
    private final RagQueryLogRepository ragQueryLogRepository;

    public WithdrawalService(
            UserRepository userRepository,
            TripRepository tripRepository,
            TripDayRepository tripDayRepository,
            TripItemRepository tripItemRepository,
            RagQueryLogRepository ragQueryLogRepository
    ) {
        this.userRepository = userRepository;
        this.tripRepository = tripRepository;
        this.tripDayRepository = tripDayRepository;
        this.tripItemRepository = tripItemRepository;
        this.ragQueryLogRepository = ragQueryLogRepository;
    }

    @Transactional
    public void withdraw(String email) {
        User user = userRepository.findByEmail(email)
                .filter(found -> !found.isWithdrawn())
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.UNAUTHORIZED, "사용자를 찾을 수 없습니다."));
        user.withdraw();
    }

    // 관리자 복구: 보관 기간 안에 탈퇴를 취소한다
    @Transactional
    public void restore(Long userId) {
        User user = userRepository.findById(userId)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "회원을 찾을 수 없습니다."));
        if (!user.isWithdrawn()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "탈퇴한 회원이 아닙니다.");
        }
        user.restore();
    }

    // 매시 정각에 보관 기간이 지난 탈퇴 회원을 파기한다 (FK 순서: 챗봇 로그 → 일정 항목 → 일차 → 여행 → 회원)
    @Scheduled(cron = "0 0 * * * *")
    @Transactional
    public void purgeExpired() {
        List<User> expired = userRepository.findByWithdrawnAtBefore(LocalDateTime.now().minusDays(RETENTION_DAYS));
        for (User user : expired) {
            Long userId = user.getUserId();
            ragQueryLogRepository.deleteAllOfUser(userId);
            tripItemRepository.deleteAllOfUser(userId);
            tripDayRepository.deleteAllOfUser(userId);
            tripRepository.deleteAllOfUser(userId);
            userRepository.delete(user);
        }
        if (!expired.isEmpty()) {
            log.info("탈퇴 후 {}일이 지난 회원 {}명의 데이터를 파기했습니다.", RETENTION_DAYS, expired.size());
        }
    }
}
