package com.triplanner.backend.repository;

import com.triplanner.backend.domain.TripChecklistItem;
import java.util.List;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

public interface TripChecklistItemRepository extends JpaRepository<TripChecklistItem, Long> {

    List<TripChecklistItem> findByTrip_TripIdOrderByDueOffsetDaysDescSortOrderAscItemIdAsc(Long tripId);

    // 여행 삭제용
    @Modifying
    @Query("delete from TripChecklistItem c where c.trip.tripId = :tripId")
    int deleteAllOfTrip(@Param("tripId") Long tripId);

    // 회원 파기용
    @Modifying
    @Query("delete from TripChecklistItem c where c.trip.tripId in (select t.tripId from Trip t where t.user.userId = :userId)")
    int deleteAllOfUser(@Param("userId") Long userId);
}
