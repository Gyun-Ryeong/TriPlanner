package com.triplanner.backend.repository;

import com.triplanner.backend.domain.TripItem;
import java.util.List;
import org.springframework.data.jpa.repository.JpaRepository;

public interface TripItemRepository extends JpaRepository<TripItem, Long> {

    List<TripItem> findByTripDay_TripDayIdOrderByVisitOrderAsc(Long tripDayId);
}
