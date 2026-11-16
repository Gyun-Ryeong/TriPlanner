package com.triplanner.backend.repository;

import com.triplanner.backend.domain.TripItem;
import java.util.List;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

public interface TripItemRepository extends JpaRepository<TripItem, Long> {

    List<TripItem> findByTripDay_TripDayIdOrderByVisitOrderAsc(Long tripDayId);

    // 챗봇 취향 요약용: 회원이 저장한 여행의 장소 (최근에 넣은 것부터)
    @Query("select i from TripItem i join fetch i.place join fetch i.tripDay d join fetch d.trip t"
            + " where t.user.email = :email order by i.tripItemId desc")
    List<TripItem> findRecentWithPlaceByEmail(@Param("email") String email, Pageable pageable);

    // 회원 파기용
    @Modifying
    @Query("delete from TripItem i where i.tripDay.tripDayId in"
            + " (select d.tripDayId from TripDay d where d.trip.user.userId = :userId)")
    int deleteAllOfUser(@Param("userId") Long userId);
}
