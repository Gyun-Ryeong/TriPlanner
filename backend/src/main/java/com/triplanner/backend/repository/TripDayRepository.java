package com.triplanner.backend.repository;

import com.triplanner.backend.domain.TripDay;
import java.util.List;
import org.springframework.data.jpa.repository.JpaRepository;

public interface TripDayRepository extends JpaRepository<TripDay, Long> {

    List<TripDay> findByTrip_TripIdOrderByDayNumberAsc(Long tripId);
}
