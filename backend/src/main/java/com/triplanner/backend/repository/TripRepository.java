package com.triplanner.backend.repository;

import com.triplanner.backend.domain.Trip;
import java.util.List;
import org.springframework.data.jpa.repository.JpaRepository;

public interface TripRepository extends JpaRepository<Trip, Long> {

    List<Trip> findByUser_UserId(Long userId);
}
