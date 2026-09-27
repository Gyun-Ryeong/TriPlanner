package com.triplanner.backend.repository;

import com.triplanner.backend.domain.Festival;
import java.util.List;
import org.springframework.data.jpa.repository.JpaRepository;

public interface FestivalRepository extends JpaRepository<Festival, Long> {

    List<Festival> findByPlace_PlaceId(Long placeId);
}
