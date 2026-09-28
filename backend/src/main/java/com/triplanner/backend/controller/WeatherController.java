package com.triplanner.backend.controller;

import com.triplanner.backend.dto.RegionWeatherResponse;
import com.triplanner.backend.service.WeatherService;
import java.util.List;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/weather")
public class WeatherController {

    private final WeatherService weatherService;

    public WeatherController(WeatherService weatherService) {
        this.weatherService = weatherService;
    }

    @GetMapping
    public ResponseEntity<List<RegionWeatherResponse>> getRegionWeather() {
        return ResponseEntity.ok(weatherService.getRegionWeather());
    }
}
