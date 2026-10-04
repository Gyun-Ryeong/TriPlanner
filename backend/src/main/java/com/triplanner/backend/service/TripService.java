package com.triplanner.backend.service;

import com.triplanner.backend.domain.Place;
import com.triplanner.backend.domain.Trip;
import com.triplanner.backend.domain.TripDay;
import com.triplanner.backend.domain.TripItem;
import com.triplanner.backend.domain.User;
import com.triplanner.backend.dto.TripCreateRequest;
import com.triplanner.backend.dto.TripDayResponse;
import com.triplanner.backend.dto.TripDetailResponse;
import com.triplanner.backend.dto.TripItemRequest;
import com.triplanner.backend.dto.TripItemResponse;
import com.triplanner.backend.dto.TripSummaryResponse;
import com.triplanner.backend.dto.TripUpdateRequest;
import com.triplanner.backend.repository.PlaceRepository;
import com.triplanner.backend.repository.TripDayRepository;
import com.triplanner.backend.repository.TripItemRepository;
import com.triplanner.backend.repository.TripRepository;
import com.triplanner.backend.repository.UserRepository;
import java.time.LocalDate;
import java.util.List;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;

@Service
@Transactional
public class TripService {

    private static final String DEFAULT_STATUS = "PLANNED";

    private final TripRepository tripRepository;
    private final TripDayRepository tripDayRepository;
    private final TripItemRepository tripItemRepository;
    private final PlaceRepository placeRepository;
    private final UserRepository userRepository;

    public TripService(
            TripRepository tripRepository,
            TripDayRepository tripDayRepository,
            TripItemRepository tripItemRepository,
            PlaceRepository placeRepository,
            UserRepository userRepository
    ) {
        this.tripRepository = tripRepository;
        this.tripDayRepository = tripDayRepository;
        this.tripItemRepository = tripItemRepository;
        this.placeRepository = placeRepository;
        this.userRepository = userRepository;
    }

    public TripSummaryResponse createTrip(String email, TripCreateRequest request) {
        User user = currentUser(email);
        validateDateRange(request.startDate(), request.endDate());

        Trip trip = new Trip(user, request.title(), request.region(), request.startDate(), request.endDate(), DEFAULT_STATUS);
        Trip saved = tripRepository.save(trip);
        generateDays(saved, request.startDate(), request.endDate());

        return toSummary(saved);
    }

    public List<TripSummaryResponse> getMyTrips(String email) {
        User user = currentUser(email);
        return tripRepository.findByUser_UserIdOrderByStartDateAsc(user.getUserId()).stream()
                .map(this::toSummary)
                .toList();
    }

    public TripDetailResponse getTrip(String email, Long tripId) {
        Trip trip = getOwnedTrip(email, tripId);
        return toDetail(trip);
    }

    public TripDetailResponse updateTrip(String email, Long tripId, TripUpdateRequest request) {
        Trip trip = getOwnedTrip(email, tripId);
        validateDateRange(request.startDate(), request.endDate());

        boolean datesChanged = !trip.getStartDate().equals(request.startDate())
                || !trip.getEndDate().equals(request.endDate());

        trip.updateDetails(request.title(), request.region(), request.startDate(), request.endDate(), request.status());

        if (datesChanged) {
            deleteDaysAndItems(trip);
            generateDays(trip, request.startDate(), request.endDate());
        }

        return toDetail(trip);
    }

    public void deleteTrip(String email, Long tripId) {
        Trip trip = getOwnedTrip(email, tripId);
        deleteDaysAndItems(trip);
        tripRepository.delete(trip);
    }

    public TripItemResponse addItem(String email, Long tripId, Long tripDayId, TripItemRequest request) {
        Trip trip = getOwnedTrip(email, tripId);
        TripDay day = getDayInTrip(trip, tripDayId);
        Place place = resolvePlace(request.placeId());

        TripItem item = new TripItem(day, place, request.itemType(), request.visitOrder(), request.startTime(), request.memo());
        TripItem saved = tripItemRepository.save(item);
        return toItemResponse(saved);
    }

    public TripItemResponse updateItem(String email, Long tripId, Long tripDayId, Long itemId, TripItemRequest request) {
        Trip trip = getOwnedTrip(email, tripId);
        TripDay day = getDayInTrip(trip, tripDayId);
        TripItem item = getItemInDay(day, itemId);
        Place place = resolvePlace(request.placeId());

        item.updateDetails(place, request.itemType(), request.visitOrder(), request.startTime(), request.memo());
        return toItemResponse(item);
    }

    public void deleteItem(String email, Long tripId, Long tripDayId, Long itemId) {
        Trip trip = getOwnedTrip(email, tripId);
        TripDay day = getDayInTrip(trip, tripDayId);
        TripItem item = getItemInDay(day, itemId);
        tripItemRepository.delete(item);
    }

    @Transactional(readOnly = true)
    public List<TripItemResponse> getDayItems(String email, Long tripId, Long tripDayId) {
        Trip trip = getOwnedTrip(email, tripId);
        TripDay day = getDayInTrip(trip, tripDayId);
        return tripItemRepository.findByTripDay_TripDayIdOrderByVisitOrderAsc(day.getTripDayId()).stream()
                .map(this::toItemResponse)
                .toList();
    }

    private User currentUser(String email) {
        return userRepository.findByEmail(email)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.UNAUTHORIZED, "사용자를 찾을 수 없습니다."));
    }

    private Trip getOwnedTrip(String email, Long tripId) {
        User user = currentUser(email);
        Trip trip = tripRepository.findById(tripId)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "여행을 찾을 수 없습니다."));

        if (!trip.getUser().getUserId().equals(user.getUserId())) {
            throw new ResponseStatusException(HttpStatus.FORBIDDEN, "본인의 여행만 이용할 수 있습니다.");
        }
        return trip;
    }

    private TripDay getDayInTrip(Trip trip, Long tripDayId) {
        TripDay day = tripDayRepository.findById(tripDayId)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "일정을 찾을 수 없습니다."));

        if (!day.getTrip().getTripId().equals(trip.getTripId())) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND, "일정을 찾을 수 없습니다.");
        }
        return day;
    }

    private TripItem getItemInDay(TripDay day, Long itemId) {
        TripItem item = tripItemRepository.findById(itemId)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "일정 항목을 찾을 수 없습니다."));

        if (!item.getTripDay().getTripDayId().equals(day.getTripDayId())) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND, "일정 항목을 찾을 수 없습니다.");
        }
        return item;
    }

    private Place resolvePlace(Long placeId) {
        if (placeId == null) {
            return null;
        }
        return placeRepository.findById(placeId)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "장소를 찾을 수 없습니다."));
    }

    private void validateDateRange(LocalDate startDate, LocalDate endDate) {
        if (endDate.isBefore(startDate)) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "종료일은 시작일보다 빠를 수 없습니다.");
        }
    }

    private void generateDays(Trip trip, LocalDate startDate, LocalDate endDate) {
        int dayNumber = 1;
        for (LocalDate date = startDate; !date.isAfter(endDate); date = date.plusDays(1)) {
            tripDayRepository.save(new TripDay(trip, dayNumber, date));
            dayNumber++;
        }
    }

    private void deleteDaysAndItems(Trip trip) {
        List<TripDay> days = tripDayRepository.findByTrip_TripIdOrderByDayNumberAsc(trip.getTripId());
        for (TripDay day : days) {
            tripItemRepository.deleteAll(tripItemRepository.findByTripDay_TripDayIdOrderByVisitOrderAsc(day.getTripDayId()));
        }
        tripDayRepository.deleteAll(days);
    }

    private TripSummaryResponse toSummary(Trip trip) {
        return new TripSummaryResponse(
                trip.getTripId(),
                trip.getTitle(),
                trip.getRegion(),
                trip.getStartDate(),
                trip.getEndDate(),
                trip.getStatus()
        );
    }

    private TripDetailResponse toDetail(Trip trip) {
        List<TripDayResponse> days = tripDayRepository.findByTrip_TripIdOrderByDayNumberAsc(trip.getTripId()).stream()
                .map(day -> new TripDayResponse(
                        day.getTripDayId(),
                        day.getDayNumber(),
                        day.getDate(),
                        tripItemRepository.findByTripDay_TripDayIdOrderByVisitOrderAsc(day.getTripDayId()).stream()
                                .map(this::toItemResponse)
                                .toList()
                ))
                .toList();

        return new TripDetailResponse(
                trip.getTripId(),
                trip.getTitle(),
                trip.getRegion(),
                trip.getStartDate(),
                trip.getEndDate(),
                trip.getStatus(),
                days
        );
    }

    private TripItemResponse toItemResponse(TripItem item) {
        Place place = item.getPlace();
        return new TripItemResponse(
                item.getTripItemId(),
                place != null ? place.getPlaceId() : null,
                place != null ? place.getContentId() : null,
                place != null ? place.getName() : null,
                place != null && place.getLatitude() != null ? place.getLatitude().doubleValue() : null,
                place != null && place.getLongitude() != null ? place.getLongitude().doubleValue() : null,
                item.getItemType(),
                item.getVisitOrder(),
                item.getStartTime(),
                item.getMemo()
        );
    }
}
