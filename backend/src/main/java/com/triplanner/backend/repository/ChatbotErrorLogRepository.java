package com.triplanner.backend.repository;

import com.triplanner.backend.domain.ChatbotErrorLog;
import java.time.LocalDateTime;
import java.util.List;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

public interface ChatbotErrorLogRepository extends JpaRepository<ChatbotErrorLog, Long> {

    List<ChatbotErrorLog> findTop50ByOrderByCreatedAtDescErrorIdDesc();

    List<ChatbotErrorLog> findTop50ByCategoryOrderByCreatedAtDescErrorIdDesc(String category);

    // 분류별 건수: [category, count]
    @Query("select e.category, count(e) from ChatbotErrorLog e group by e.category")
    List<Object[]> countByCategory();

    // 보관 기간이 지난 기록 삭제
    @Modifying
    @Query("delete from ChatbotErrorLog e where e.createdAt < :before")
    int deleteOlderThan(@Param("before") LocalDateTime before);

    // 회원 파기용
    @Modifying
    @Query("delete from ChatbotErrorLog e where e.userId = :userId")
    int deleteAllOfUser(@Param("userId") Long userId);
}
