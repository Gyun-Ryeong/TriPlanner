package com.triplanner.backend.controller;

import com.triplanner.backend.dto.TripAlertsResponse;
import com.triplanner.backend.dto.TripCreateRequest;
import com.triplanner.backend.dto.TripDetailResponse;
import com.triplanner.backend.dto.TripItemRequest;
import com.triplanner.backend.dto.TripItemResponse;
import com.triplanner.backend.dto.TripSummaryResponse;
import com.triplanner.backend.dto.TripUpdateRequest;
import com.triplanner.backend.dto.RouteResponse;
import com.triplanner.backend.service.RouteService;
import com.triplanner.backend.service.TripAlertService;
import com.triplanner.backend.service.TripService;
import jakarta.validation.Valid;
import java.util.List;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/trips")
public class TripController {

    private final TripService tripService;
    private final RouteService routeService;
    private final TripAlertService tripAlertService;

    public TripController(TripService tripService, RouteService routeService, TripAlertService tripAlertService) {
        this.tripService = tripService;
        this.routeService = routeService;
        this.tripAlertService = tripAlertService;
    }

    @GetMapping("/alerts")
    public ResponseEntity<TripAlertsResponse> getTripAlerts(Authentication authentication) {
        return ResponseEntity.ok(tripAlertService.getAlerts(authentication.getName()));
    }

    @GetMapping("/{tripId}/days/{tripDayId}/route")
    public ResponseEntity<RouteResponse> getDayRoute(
            Authentication authentication,
            @PathVariable Long tripId,
            @PathVariable Long tripDayId
    ) {
        return ResponseEntity.ok(routeService.getDayRoute(authentication.getName(), tripId, tripDayId));
    }

    @PostMapping
    public ResponseEntity<TripSummaryResponse> createTrip(
            Authentication authentication,
            @Valid @RequestBody TripCreateRequest request
    ) {
        return ResponseEntity.ok(tripService.createTrip(authentication.getName(), request));
    }

    @GetMapping
    public ResponseEntity<List<TripSummaryResponse>> getMyTrips(Authentication authentication) {
        return ResponseEntity.ok(tripService.getMyTrips(authentication.getName()));
    }

    @GetMapping("/{tripId}")
    public ResponseEntity<TripDetailResponse> getTrip(Authentication authentication, @PathVariable Long tripId) {
        return ResponseEntity.ok(tripService.getTrip(authentication.getName(), tripId));
    }

    @PutMapping("/{tripId}")
    public ResponseEntity<TripDetailResponse> updateTrip(
            Authentication authentication,
            @PathVariable Long tripId,
            @Valid @RequestBody TripUpdateRequest request
    ) {
        return ResponseEntity.ok(tripService.updateTrip(authentication.getName(), tripId, request));
    }

    @DeleteMapping("/{tripId}")
    public ResponseEntity<Void> deleteTrip(Authentication authentication, @PathVariable Long tripId) {
        tripService.deleteTrip(authentication.getName(), tripId);
        return ResponseEntity.noContent().build();
    }

    @PostMapping("/{tripId}/days/{tripDayId}/items")
    public ResponseEntity<TripItemResponse> addItem(
            Authentication authentication,
            @PathVariable Long tripId,
            @PathVariable Long tripDayId,
            @Valid @RequestBody TripItemRequest request
    ) {
        return ResponseEntity.ok(tripService.addItem(authentication.getName(), tripId, tripDayId, request));
    }

    @PutMapping("/{tripId}/days/{tripDayId}/items/{itemId}")
    public ResponseEntity<TripItemResponse> updateItem(
            Authentication authentication,
            @PathVariable Long tripId,
            @PathVariable Long tripDayId,
            @PathVariable Long itemId,
            @Valid @RequestBody TripItemRequest request
    ) {
        return ResponseEntity.ok(tripService.updateItem(authentication.getName(), tripId, tripDayId, itemId, request));
    }

    @DeleteMapping("/{tripId}/days/{tripDayId}/items/{itemId}")
    public ResponseEntity<Void> deleteItem(
            Authentication authentication,
            @PathVariable Long tripId,
            @PathVariable Long tripDayId,
            @PathVariable Long itemId
    ) {
        tripService.deleteItem(authentication.getName(), tripId, tripDayId, itemId);
        return ResponseEntity.noContent().build();
    }
}
