package com.triplanner.backend.repository;

import com.triplanner.backend.domain.FestivalSchedule;
import java.util.List;
import org.springframework.data.jpa.repository.JpaRepository;

public interface FestivalScheduleRepository extends JpaRepository<FestivalSchedule, Long> {

    List<FestivalSchedule> findByFestival_FestivalId(Long festivalId);
}
