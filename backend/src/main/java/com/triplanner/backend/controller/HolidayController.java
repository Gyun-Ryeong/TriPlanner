package com.triplanner.backend.controller;

import com.triplanner.backend.dto.HolidayResponse;
import com.triplanner.backend.service.HolidayService;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

// 달력에 표시할 공휴일 (공개 정보라 로그인 없이 볼 수 있다)
@RestController
@RequestMapping("/api/holidays")
public class HolidayController {

    private final HolidayService holidayService;

    public HolidayController(HolidayService holidayService) {
        this.holidayService = holidayService;
    }

    @GetMapping
    public ResponseEntity<HolidayResponse> getMonth(@RequestParam int year, @RequestParam int month) {
        return ResponseEntity.ok(holidayService.getMonth(year, month));
    }
}
