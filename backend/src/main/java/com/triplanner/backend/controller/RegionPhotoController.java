package com.triplanner.backend.controller;

import com.triplanner.backend.dto.RegionPhotoResponse;
import com.triplanner.backend.service.RegionPhotoService;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

// 여행 목록의 지역 사진 (앱에 사진 파일이 없는 시·군만 프론트가 부른다)
@RestController
@RequestMapping("/api/regions")
public class RegionPhotoController {

    private final RegionPhotoService regionPhotoService;

    public RegionPhotoController(RegionPhotoService regionPhotoService) {
        this.regionPhotoService = regionPhotoService;
    }

    @GetMapping("/photo")
    public ResponseEntity<RegionPhotoResponse> getPhoto(
            @RequestParam String name,
            @RequestParam(required = false, defaultValue = "") String region
    ) {
        return ResponseEntity.ok(regionPhotoService.getPhoto(name, region));
    }
}
