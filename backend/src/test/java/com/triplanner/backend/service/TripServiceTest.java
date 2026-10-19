package com.triplanner.backend.service;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.triplanner.backend.domain.Trip;
import com.triplanner.backend.domain.TripDay;
import com.triplanner.backend.domain.TripItem;
import com.triplanner.backend.domain.User;
import com.triplanner.backend.dto.TripCreateRequest;
import com.triplanner.backend.repository.PlaceRepository;
import com.triplanner.backend.repository.TripChecklistItemRepository;
import com.triplanner.backend.repository.TripDayRepository;
import com.triplanner.backend.repository.TripItemRepository;
import com.triplanner.backend.repository.TripRepository;
import com.triplanner.backend.repository.UserRepository;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.List;
import java.util.Optional;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.springframework.http.HttpStatus;
import org.springframework.web.server.ResponseStatusException;

class TripServiceTest {

    private static final String EMAIL = "member@test.local";
    private static final LocalDate START = LocalDate.of(2026, 10, 20);

    private TripRepository tripRepository;
    private TripDayRepository tripDayRepository;
    private TripItemRepository tripItemRepository;
    private TripService service;
    private Trip trip;
    private List<TripDay> days;

    @BeforeEach
    void setUp() {
        tripRepository = mock(TripRepository.class);
        tripDayRepository = mock(TripDayRepository.class);
        tripItemRepository = mock(TripItemRepository.class);
        UserRepository userRepository = mock(UserRepository.class);
        service = new TripService(
                tripRepository,
                tripDayRepository,
                tripItemRepository,
                mock(PlaceRepository.class),
                userRepository,
                mock(TripChecklistItemRepository.class));

        User user = mock(User.class);
        when(user.getUserId()).thenReturn(1L);
        when(userRepository.findByEmail(EMAIL)).thenReturn(Optional.of(user));

        // 2박 3일 (10/20 ~ 10/22)
        trip = new Trip(user, "가을 여행", "제주도", START, START.plusDays(2), "PLANNED");
        days = new ArrayList<>(List.of(
                new TripDay(trip, 1, START),
                new TripDay(trip, 2, START.plusDays(1)),
                new TripDay(trip, 3, START.plusDays(2))));
        when(tripRepository.findById(any())).thenReturn(Optional.of(trip));
        when(tripDayRepository.findByTrip_TripIdOrderByDayNumberAsc(any())).thenReturn(days);
        when(tripItemRepository.findByTripDay_TripDayIdOrderByVisitOrderAsc(any())).thenReturn(List.of());
    }

    private TripCreateRequest createRequest(String region, String city) {
        return new TripCreateRequest("새 여행", region, city, START, START.plusDays(1));
    }

    @Test
    void createTripStoresTheChosenCityOfThatRegion() {
        when(tripRepository.save(any(Trip.class))).thenAnswer(invocation -> invocation.getArgument(0));

        service.createTrip(EMAIL, createRequest("제주도", " 서귀포 "));

        ArgumentCaptor<Trip> saved = ArgumentCaptor.forClass(Trip.class);
        verify(tripRepository).save(saved.capture());
        assertEquals("서귀포", saved.getValue().getCity());
    }

    @Test
    void createTripWithoutCityKeepsItEmpty() {
        when(tripRepository.save(any(Trip.class))).thenAnswer(invocation -> invocation.getArgument(0));

        service.createTrip(EMAIL, createRequest("제주도", ""));

        ArgumentCaptor<Trip> saved = ArgumentCaptor.forClass(Trip.class);
        verify(tripRepository).save(saved.capture());
        assertEquals(null, saved.getValue().getCity());
    }

    @Test
    void createTripRejectsACityThatIsNotInTheRegion() {
        ResponseStatusException failure = assertThrows(ResponseStatusException.class,
                () -> service.createTrip(EMAIL, createRequest("제주도", "부산")));

        assertEquals(HttpStatus.BAD_REQUEST, failure.getStatusCode());
        verify(tripRepository, never()).save(any(Trip.class));
    }

    private TripItem item() {
        return new TripItem(days.get(2), null, "메모", 1, null, "공항 가기");
    }

    @Test
    void addDayAppendsTheNextDayAndMovesEndDate() {
        service.addDay(EMAIL, 1L);

        ArgumentCaptor<TripDay> saved = ArgumentCaptor.forClass(TripDay.class);
        verify(tripDayRepository).save(saved.capture());
        assertEquals(4, saved.getValue().getDayNumber());
        assertEquals(START.plusDays(3), saved.getValue().getDate());
        assertEquals(START.plusDays(3), trip.getEndDate());
    }

    @Test
    void addDayStopsAtThirtyOneDays() {
        while (days.size() < 31) {
            days.add(new TripDay(trip, days.size() + 1, START.plusDays(days.size())));
        }

        ResponseStatusException failure = assertThrows(ResponseStatusException.class, () -> service.addDay(EMAIL, 1L));

        assertEquals(HttpStatus.BAD_REQUEST, failure.getStatusCode());
        verify(tripDayRepository, never()).save(any());
    }

    @Test
    void removeLastDayWithoutItemsDeletesItAndMovesEndDateBack() {
        service.removeLastDay(EMAIL, 1L, false);

        verify(tripDayRepository).delete(days.get(2));
        assertEquals(START.plusDays(1), trip.getEndDate());
    }

    @Test
    void removeLastDayWithItemsNeedsConfirmation() {
        when(tripItemRepository.findByTripDay_TripDayIdOrderByVisitOrderAsc(any())).thenReturn(List.of(item()));

        ResponseStatusException failure = assertThrows(ResponseStatusException.class,
                () -> service.removeLastDay(EMAIL, 1L, false));

        assertEquals(HttpStatus.CONFLICT, failure.getStatusCode());
        verify(tripDayRepository, never()).delete(any(TripDay.class));
        verify(tripItemRepository, never()).deleteAll(any());
        assertEquals(START.plusDays(2), trip.getEndDate());
    }

    @Test
    void removeLastDayWithItemsDeletesThemOnceConfirmed() {
        TripItem planned = item();
        when(tripItemRepository.findByTripDay_TripDayIdOrderByVisitOrderAsc(any())).thenReturn(List.of(planned));

        service.removeLastDay(EMAIL, 1L, true);

        verify(tripItemRepository).deleteAll(List.of(planned));
        verify(tripDayRepository).delete(days.get(2));
        assertEquals(START.plusDays(1), trip.getEndDate());
    }

    @Test
    void theOnlyRemainingDayCannotBeRemoved() {
        days.subList(1, 3).clear();

        ResponseStatusException failure = assertThrows(ResponseStatusException.class,
                () -> service.removeLastDay(EMAIL, 1L, true));

        assertEquals(HttpStatus.BAD_REQUEST, failure.getStatusCode());
        verify(tripDayRepository, never()).delete(any(TripDay.class));
    }
}
