package com.triplanner.backend.controller;

import com.triplanner.backend.dto.FestivalCalendarResponse;
import com.triplanner.backend.dto.FestivalDetailResponse;
import com.triplanner.backend.service.FestivalService;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

// 축제 달력 (공개 정보라 로그인 없이 볼 수 있다)
@RestController
@RequestMapping("/api/festivals")
public class FestivalController {

    private final FestivalService festivalService;

    public FestivalController(FestivalService festivalService) {
        this.festivalService = festivalService;
    }

    @GetMapping
    public ResponseEntity<FestivalCalendarResponse> getMonth(
            @RequestParam String sido,
            @RequestParam int year,
            @RequestParam int month
    ) {
        return ResponseEntity.ok(festivalService.getMonth(sido, year, month));
    }

    @GetMapping("/{contentId}")
    public ResponseEntity<FestivalDetailResponse> getDetail(@PathVariable String contentId) {
        return ResponseEntity.ok(festivalService.getDetail(contentId));
    }
}
