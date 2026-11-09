package com.triplanner.backend.controller;

import com.triplanner.backend.dto.SharedTripResponse;
import com.triplanner.backend.service.TripService;
import org.springframework.http.CacheControl;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

// 공유 링크로 여행을 보는 공개 API (로그인 없이, 읽기만 가능)
@RestController
@RequestMapping("/api/shared")
public class SharedTripController {

    private final TripService tripService;

    public SharedTripController(TripService tripService) {
        this.tripService = tripService;
    }

    @GetMapping("/{shareCode}")
    public ResponseEntity<SharedTripResponse> getSharedTrip(@PathVariable String shareCode) {
        // 공유를 멈춘 링크가 브라우저나 중간 캐시에 남아 계속 열리지 않도록 저장하지 않게 한다
        return ResponseEntity.ok().cacheControl(CacheControl.noStore()).body(tripService.getSharedTrip(shareCode));
    }
}
