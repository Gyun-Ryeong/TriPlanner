package com.triplanner.backend.repository;

import com.triplanner.backend.domain.RagQueryLog;
import java.util.List;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

public interface RagQueryLogRepository extends JpaRepository<RagQueryLog, Long> {

    List<RagQueryLog> findByTrip_TripIdOrderByCreatedAtAsc(Long tripId);

    // 회원 파기용: 회원이 남긴 로그와 회원의 여행에 달린 로그를 모두 지운다
    @Modifying
    @Query("delete from RagQueryLog l where l.user.userId = :userId"
            + " or l.trip.tripId in (select t.tripId from Trip t where t.user.userId = :userId)")
    int deleteAllOfUser(@Param("userId") Long userId);
}
