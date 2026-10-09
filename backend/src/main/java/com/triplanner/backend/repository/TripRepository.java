package com.triplanner.backend.repository;

import com.triplanner.backend.domain.Trip;
import java.util.List;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;

public interface TripRepository extends JpaRepository<Trip, Long> {

    List<Trip> findByUser_UserIdOrderByStartDateAsc(Long userId);

    // 관리자 회원 목록용: [userId, 여행 수]
    @Query("select t.user.userId, count(t) from Trip t group by t.user.userId")
    List<Object[]> countTripsByUser();
}
