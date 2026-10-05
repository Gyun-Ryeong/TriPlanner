package com.triplanner.backend.controller;

import com.triplanner.backend.dto.RegionWeatherResponse;
import com.triplanner.backend.dto.WeatherWarningResponse;
import com.triplanner.backend.service.WeatherService;
import com.triplanner.backend.service.WeatherWarningService;
import java.util.List;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/weather")
public class WeatherController {

    private final WeatherService weatherService;

    private final WeatherWarningService weatherWarningService;

    public WeatherController(WeatherService weatherService, WeatherWarningService weatherWarningService) {
        this.weatherService = weatherService;
        this.weatherWarningService = weatherWarningService;
    }

    @GetMapping
    public ResponseEntity<List<RegionWeatherResponse>> getRegionWeather() {
        return ResponseEntity.ok(weatherService.getRegionWeather());
    }

    @GetMapping("/warnings")
    public ResponseEntity<WeatherWarningResponse> getActiveWarnings() {
        return ResponseEntity.ok(weatherWarningService.getActiveWarnings());
    }
}
