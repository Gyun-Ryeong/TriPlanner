package com.triplanner.backend.controller;

import com.triplanner.backend.dto.PlaceResponse;
import com.triplanner.backend.dto.PlaceSaveRequest;
import com.triplanner.backend.dto.PlaceSearchResult;
import com.triplanner.backend.service.PlaceService;
import jakarta.validation.Valid;
import java.util.List;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/places")
public class PlaceController {

    private final PlaceService placeService;

    public PlaceController(PlaceService placeService) {
        this.placeService = placeService;
    }

    @GetMapping("/search")
    public ResponseEntity<List<PlaceSearchResult>> search(@RequestParam String keyword) {
        return ResponseEntity.ok(placeService.search(keyword));
    }

    @PostMapping
    public ResponseEntity<PlaceResponse> save(@Valid @RequestBody PlaceSaveRequest request) {
        return ResponseEntity.ok(placeService.save(request));
    }
}
