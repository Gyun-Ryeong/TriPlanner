package com.triplanner.backend.repository;

import com.triplanner.backend.domain.TripDay;
import java.util.List;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

public interface TripDayRepository extends JpaRepository<TripDay, Long> {

    List<TripDay> findByTrip_TripIdOrderByDayNumberAsc(Long tripId);

    // 회원 파기용
    @Modifying
    @Query("delete from TripDay d where d.trip.tripId in (select t.tripId from Trip t where t.user.userId = :userId)")
    int deleteAllOfUser(@Param("userId") Long userId);
}
