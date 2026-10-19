package com.triplanner.backend.controller;

import com.triplanner.backend.dto.ChatPlanImportRequest;
import com.triplanner.backend.dto.ChecklistCheckRequest;
import com.triplanner.backend.dto.ChecklistItemRequest;
import com.triplanner.backend.dto.ChecklistItemResponse;
import com.triplanner.backend.dto.TripAlertsResponse;
import com.triplanner.backend.dto.TripCreateRequest;
import com.triplanner.backend.dto.TripDetailResponse;
import com.triplanner.backend.dto.TripItemRequest;
import com.triplanner.backend.dto.TripItemResponse;
import com.triplanner.backend.dto.TripSummaryResponse;
import com.triplanner.backend.dto.TripUpdateRequest;
import com.triplanner.backend.dto.RouteResponse;
import com.triplanner.backend.dto.PrepAlertsResponse;
import com.triplanner.backend.service.ChecklistService;
import com.triplanner.backend.service.PrepAlertService;
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
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/trips")
public class TripController {

    private final TripService tripService;
    private final RouteService routeService;
    private final TripAlertService tripAlertService;
    private final ChecklistService checklistService;
    private final PrepAlertService prepAlertService;

    public TripController(
            TripService tripService,
            RouteService routeService,
            TripAlertService tripAlertService,
            ChecklistService checklistService,
            PrepAlertService prepAlertService
    ) {
        this.tripService = tripService;
        this.routeService = routeService;
        this.tripAlertService = tripAlertService;
        this.checklistService = checklistService;
        this.prepAlertService = prepAlertService;
    }

    // 일정 변경·준비 알림 (체크리스트 기한, 비어 있는 일정)
    @GetMapping("/prep-alerts")
    public ResponseEntity<PrepAlertsResponse> getPrepAlerts(Authentication authentication) {
        return ResponseEntity.ok(prepAlertService.getAlerts(authentication.getName()));
    }

    @GetMapping("/{tripId}/checklist")
    public ResponseEntity<List<ChecklistItemResponse>> getChecklist(Authentication authentication, @PathVariable Long tripId) {
        return ResponseEntity.ok(checklistService.getChecklist(authentication.getName(), tripId));
    }

    @PostMapping("/{tripId}/checklist")
    public ResponseEntity<ChecklistItemResponse> addChecklistItem(
            Authentication authentication,
            @PathVariable Long tripId,
            @Valid @RequestBody ChecklistItemRequest request
    ) {
        return ResponseEntity.ok(checklistService.addItem(authentication.getName(), tripId, request));
    }

    @PutMapping("/{tripId}/checklist/{itemId}")
    public ResponseEntity<ChecklistItemResponse> checkChecklistItem(
            Authentication authentication,
            @PathVariable Long tripId,
            @PathVariable Long itemId,
            @Valid @RequestBody ChecklistCheckRequest request
    ) {
        return ResponseEntity.ok(checklistService.setChecked(authentication.getName(), tripId, itemId, request.checked()));
    }

    @DeleteMapping("/{tripId}/checklist/{itemId}")
    public ResponseEntity<Void> deleteChecklistItem(
            Authentication authentication,
            @PathVariable Long tripId,
            @PathVariable Long itemId
    ) {
        checklistService.deleteItem(authentication.getName(), tripId, itemId);
        return ResponseEntity.noContent().build();
    }

    @GetMapping("/alerts")
    public ResponseEntity<TripAlertsResponse> getTripAlerts(Authentication authentication) {
        return ResponseEntity.ok(tripAlertService.getAlerts(authentication.getName()));
    }

    @GetMapping("/{tripId}/days/{tripDayId}/route")
    public ResponseEntity<RouteResponse> getDayRoute(
            Authentication authentication,
            @PathVariable Long tripId,
            @PathVariable Long tripDayId,
            @RequestParam(defaultValue = "driving") String mode
    ) {
        return ResponseEntity.ok(routeService.getDayRoute(authentication.getName(), tripId, tripDayId, mode));
    }

    @PostMapping
    public ResponseEntity<TripSummaryResponse> createTrip(
            Authentication authentication,
            @Valid @RequestBody TripCreateRequest request
    ) {
        return ResponseEntity.ok(tripService.createTrip(authentication.getName(), request));
    }

    // 챗봇이 만든 일정을 '내 여행'으로 저장
    @PostMapping("/import")
    public ResponseEntity<TripSummaryResponse> importChatPlan(
            Authentication authentication,
            @Valid @RequestBody ChatPlanImportRequest request
    ) {
        return ResponseEntity.ok(tripService.importChatPlan(authentication.getName(), request));
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

    // 마지막 일차 뒤에 하루 추가
    @PostMapping("/{tripId}/days")
    public ResponseEntity<TripDetailResponse> addDay(Authentication authentication, @PathVariable Long tripId) {
        return ResponseEntity.ok(tripService.addDay(authentication.getName(), tripId));
    }

    // 마지막 일차 삭제. 일정이 들어 있으면 confirmed=true 로 확인했을 때만 지운다 (아니면 409)
    @DeleteMapping("/{tripId}/days/last")
    public ResponseEntity<TripDetailResponse> removeLastDay(
            Authentication authentication,
            @PathVariable Long tripId,
            @RequestParam(defaultValue = "false") boolean confirmed
    ) {
        return ResponseEntity.ok(tripService.removeLastDay(authentication.getName(), tripId, confirmed));
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
