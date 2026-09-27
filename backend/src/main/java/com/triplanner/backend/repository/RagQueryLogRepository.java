package com.triplanner.backend.repository;

import com.triplanner.backend.domain.RagQueryLog;
import java.util.List;
import org.springframework.data.jpa.repository.JpaRepository;

public interface RagQueryLogRepository extends JpaRepository<RagQueryLog, Long> {

    List<RagQueryLog> findByTrip_TripIdOrderByCreatedAtAsc(Long tripId);
}
