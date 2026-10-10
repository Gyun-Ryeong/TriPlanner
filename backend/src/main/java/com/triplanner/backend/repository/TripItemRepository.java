package com.triplanner.backend.repository;

import com.triplanner.backend.domain.TripItem;
import java.util.List;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

public interface TripItemRepository extends JpaRepository<TripItem, Long> {

    List<TripItem> findByTripDay_TripDayIdOrderByVisitOrderAsc(Long tripDayId);

    // 회원 파기용
    @Modifying
    @Query("delete from TripItem i where i.tripDay.tripDayId in"
            + " (select d.tripDayId from TripDay d where d.trip.user.userId = :userId)")
    int deleteAllOfUser(@Param("userId") Long userId);
}
