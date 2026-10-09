package com.triplanner.backend.controller;

import com.triplanner.backend.dto.RegionAirQualityResponse;
import com.triplanner.backend.service.AirQualityService;
import java.util.List;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/air-quality")
public class AirQualityController {

    private final AirQualityService airQualityService;

    public AirQualityController(AirQualityService airQualityService) {
        this.airQualityService = airQualityService;
    }

    @GetMapping
    public ResponseEntity<List<RegionAirQualityResponse>> getRegionAirQuality() {
        return ResponseEntity.ok(airQualityService.getRegionAirQuality());
    }
}
