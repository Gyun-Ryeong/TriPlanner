package com.triplanner.backend.service;

import com.triplanner.backend.domain.ChatbotErrorLog;
import com.triplanner.backend.domain.User;
import com.triplanner.backend.dto.ChatbotErrorLogResponse;
import com.triplanner.backend.dto.ChatbotErrorLogResponse.Item;
import com.triplanner.backend.repository.ChatbotErrorLogRepository;
import com.triplanner.backend.repository.UserRepository;
import java.time.LocalDateTime;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.function.Function;
import java.util.stream.Collectors;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

// 챗봇 오류 기록: 사용자의 챗봇 요청이 실패하면 남기고, 관리자 페이지에서 분류별로 본다. 30일이 지나면 자동으로 지운다
@Service
public class ChatbotErrorLogService {

    public static final String CONNECTION = "CONNECTION";
    public static final String TIMEOUT = "TIMEOUT";
    public static final String AI_MODEL = "AI_MODEL";
    public static final String SERVER_ERROR = "SERVER_ERROR";
    public static final String BAD_REQUEST = "BAD_REQUEST";
    public static final String OTHER = "OTHER";

    public static final int RETENTION_DAYS = 30;
    static final int DETAIL_MAX_LENGTH = 500;
    static final int QUERY_MAX_LENGTH = 100;

    private static final Logger log = LoggerFactory.getLogger(ChatbotErrorLogService.class);

    private final ChatbotErrorLogRepository errorLogRepository;
    private final UserRepository userRepository;

    public ChatbotErrorLogService(ChatbotErrorLogRepository errorLogRepository, UserRepository userRepository) {
        this.errorLogRepository = errorLogRepository;
        this.userRepository = userRepository;
    }

    // 기록하다 실패해도 사용자에게 가는 원래 오류 응답은 그대로 나가야 하므로 예외를 밖으로 던지지 않는다
    public void record(String email, String category, Integer httpStatus, String detail, String message) {
        try {
            Long userId = email == null ? null : userRepository.findByEmail(email).map(User::getUserId).orElse(null);
            errorLogRepository.save(new ChatbotErrorLog(
                    userId, category, httpStatus, truncate(detail, DETAIL_MAX_LENGTH), truncate(message, QUERY_MAX_LENGTH)));
        } catch (RuntimeException e) {
            log.warn("챗봇 오류 기록을 저장하지 못했습니다: {}", e.getMessage());
        }
    }

    @Transactional(readOnly = true)
    public ChatbotErrorLogResponse list(String category) {
        Map<String, Long> counts = new LinkedHashMap<>();
        for (Object[] row : errorLogRepository.countByCategory()) {
            counts.put((String) row[0], (Long) row[1]);
        }
        long total = counts.values().stream().mapToLong(Long::longValue).sum();

        boolean all = category == null || category.isBlank();
        List<ChatbotErrorLog> logs = all
                ? errorLogRepository.findTop50ByOrderByCreatedAtDescErrorIdDesc()
                : errorLogRepository.findTop50ByCategoryOrderByCreatedAtDescErrorIdDesc(category);

        List<Long> userIds = logs.stream().map(ChatbotErrorLog::getUserId).filter(id -> id != null).distinct().toList();
        Map<Long, User> users = userRepository.findAllById(userIds).stream()
                .collect(Collectors.toMap(User::getUserId, Function.identity()));

        List<Item> items = logs.stream().map(entry -> {
            User user = entry.getUserId() == null ? null : users.get(entry.getUserId());
            return new Item(
                    entry.getErrorId(),
                    entry.getCreatedAt(),
                    entry.getUserId(),
                    user == null ? null : user.getEmail(),
                    user == null ? null : user.getNickname(),
                    entry.getCategory(),
                    entry.getHttpStatus(),
                    entry.getDetail(),
                    entry.getQueryPreview()
            );
        }).toList();
        return new ChatbotErrorLogResponse(total, counts, items);
    }

    @Transactional
    public void clearAll() {
        errorLogRepository.deleteAllInBatch();
    }

    // 매시 30분에 보관 기간(30일)이 지난 기록을 지운다
    @Scheduled(cron = "0 30 * * * *")
    @Transactional
    public void purgeExpired() {
        int deleted = errorLogRepository.deleteOlderThan(LocalDateTime.now().minusDays(RETENTION_DAYS));
        if (deleted > 0) {
            log.info("{}일이 지난 챗봇 오류 기록 {}건을 지웠습니다.", RETENTION_DAYS, deleted);
        }
    }

    static String truncate(String value, int maxLength) {
        if (value == null || value.isBlank()) {
            return null;
        }
        String trimmed = value.strip();
        return trimmed.length() <= maxLength ? trimmed : trimmed.substring(0, maxLength);
    }
}
