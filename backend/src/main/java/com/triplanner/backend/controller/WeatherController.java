package com.triplanner.backend.controller;

import com.triplanner.backend.dto.RegionCatalogResponse;
import com.triplanner.backend.dto.RegionWeatherResponse;
import com.triplanner.backend.dto.WeatherWarningResponse;
import com.triplanner.backend.service.RegionCatalog;
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

    // 권역과 도시 이름 목록 (여행 만들기의 세부 지역 선택용, 외부 호출 없음)
    @GetMapping("/regions")
    public ResponseEntity<List<RegionCatalogResponse>> getRegions() {
        return ResponseEntity.ok(RegionCatalog.REGIONS.stream()
                .map(r -> new RegionCatalogResponse(r.id(), r.name(), r.cities().stream().map(RegionCatalog.CityGrid::name).toList()))
                .toList());
    }

    @GetMapping("/warnings")
    public ResponseEntity<WeatherWarningResponse> getActiveWarnings() {
        return ResponseEntity.ok(weatherWarningService.getActiveWarnings());
    }
}
