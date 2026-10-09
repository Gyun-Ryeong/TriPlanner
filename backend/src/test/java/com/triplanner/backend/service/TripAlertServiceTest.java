package com.triplanner.backend.service;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.triplanner.backend.domain.Trip;
import com.triplanner.backend.domain.User;
import com.triplanner.backend.dto.AirForecast;
import com.triplanner.backend.dto.DailyForecast;
import com.triplanner.backend.dto.TripAlertsResponse;
import com.triplanner.backend.dto.TripAlertsResponse.Alert;
import com.triplanner.backend.dto.TripAlertsResponse.TripAlerts;
import com.triplanner.backend.dto.WeatherWarningResponse;
import com.triplanner.backend.dto.WeatherWarningResponse.Warning;
import com.triplanner.backend.repository.TripRepository;
import com.triplanner.backend.repository.UserRepository;
import java.time.LocalDate;
import java.time.ZoneId;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.web.server.ResponseStatusException;

class TripAlertServiceTest {

    private static final LocalDate TODAY = LocalDate.now(ZoneId.of("Asia/Seoul"));

    private TripRepository tripRepository;
    private WeatherService weatherService;
    private AirQualityService airQualityService;
    private WeatherWarningService weatherWarningService;
    private TripAlertService service;
    private User user;

    @BeforeEach
    void setUp() {
        tripRepository = mock(TripRepository.class);
        UserRepository userRepository = mock(UserRepository.class);
        weatherService = mock(WeatherService.class);
        airQualityService = mock(AirQualityService.class);
        weatherWarningService = mock(WeatherWarningService.class);

        User user = mock(User.class);
        when(user.getUserId()).thenReturn(1L);
        when(user.isNotifyTripAlerts()).thenReturn(true);
        when(userRepository.findByEmail(anyString())).thenReturn(Optional.of(user));
        this.user = user;

        // 기본값: 날씨 좋음, 대기질 좋음, 특보 없음
        when(weatherService.getDailyForecasts(anyString())).thenReturn(List.of(calm(TODAY)));
        when(airQualityService.getForecast()).thenReturn(air("PM10", TODAY, "서울", "좋음"));
        when(weatherWarningService.getActiveWarnings()).thenReturn(new WeatherWarningResponse(null, List.of()));

        service = new TripAlertService(tripRepository, userRepository, weatherService, airQualityService, weatherWarningService);
    }

    private void givenTrip(String region, int startOffset, int endOffset) {
        User owner = mock(User.class);
        Trip trip = new Trip(owner, "테스트 여행", region, TODAY.plusDays(startOffset), TODAY.plusDays(endOffset), "PLANNED");
        when(tripRepository.findByUser_UserIdOrderByStartDateAsc(1L)).thenReturn(List.of(trip));
    }

    private static DailyForecast calm(LocalDate date) {
        return new DailyForecast(date, 15, 22, 10, false, false, 0, 0);
    }

    private static AirForecast air(String code, LocalDate date, String area, String grade) {
        return new AirForecast(Map.of(code, Map.of(date, Map.of(area, grade))));
    }

    private List<Alert> alertsOfOnlyTrip() {
        TripAlertsResponse response = service.getAlerts("a@test.local");
        assertThat(response.trips()).hasSize(1);
        return response.trips().get(0).alerts();
    }

    @Test
    void userWhoTurnedAlertsOffGetsDisabledResponseWithoutAnyExternalCall() {
        givenTrip("서울 특별시", 0, 1);
        when(user.isNotifyTripAlerts()).thenReturn(false);

        TripAlertsResponse response = service.getAlerts("a@test.local");
        assertThat(response.alertsEnabled()).isFalse();
        assertThat(response.trips()).isEmpty();
        verify(weatherService, never()).getDailyForecasts(anyString());
        verify(airQualityService, never()).getForecast();
        verify(weatherWarningService, never()).getActiveWarnings();
    }

    @Test
    void calmDayProducesNoAlerts() {
        givenTrip("서울 특별시", 0, 1);
        assertThat(alertsOfOnlyTrip()).isEmpty();
    }

    @Test
    void rainOrHighProbabilityIsCaution() {
        givenTrip("서울 특별시", 0, 0);
        when(weatherService.getDailyForecasts("seoul")).thenReturn(List.of(new DailyForecast(TODAY, 15, 22, 70, true, false, 2, 0)));

        List<Alert> alerts = alertsOfOnlyTrip();
        assertThat(alerts).hasSize(1);
        assertThat(alerts.get(0).level()).isEqualTo("CAUTION");
        assertThat(alerts.get(0).kind()).isEqualTo("PRECIPITATION");
        assertThat(alerts.get(0).message()).contains("비 예보예요 (강수확률 70%)");

        // 비 예보는 없어도 강수확률만 50% 이상이면 주의
        when(weatherService.getDailyForecasts("seoul")).thenReturn(List.of(new DailyForecast(TODAY, 15, 22, 50, false, false, 0, 0)));
        assertThat(alertsOfOnlyTrip()).hasSize(1);

        // 49%는 알림 없음
        when(weatherService.getDailyForecasts("seoul")).thenReturn(List.of(new DailyForecast(TODAY, 15, 22, 49, false, false, 0, 0)));
        assertThat(alertsOfOnlyTrip()).isEmpty();
    }

    @Test
    void heavyRainAndHeavySnowAreDanger() {
        givenTrip("서울 특별시", 0, 0);
        when(weatherService.getDailyForecasts("seoul")).thenReturn(List.of(new DailyForecast(TODAY, 15, 22, 90, true, false, 30.0, 0)));
        List<Alert> rain = alertsOfOnlyTrip();
        assertThat(rain).hasSize(1); // 주의와 위험이 겹쳐 두 개가 나오면 안 된다
        assertThat(rain.get(0).level()).isEqualTo("DANGER");
        assertThat(rain.get(0).message()).contains("30mm");

        when(weatherService.getDailyForecasts("seoul")).thenReturn(List.of(new DailyForecast(TODAY, -2, 1, 90, false, true, 0, 5.0)));
        List<Alert> snow = alertsOfOnlyTrip();
        assertThat(snow).hasSize(1);
        assertThat(snow.get(0).level()).isEqualTo("DANGER");
    }

    @Test
    void temperatureThresholds() {
        givenTrip("서울 특별시", 0, 0);

        when(weatherService.getDailyForecasts("seoul")).thenReturn(List.of(new DailyForecast(TODAY, 20, 33, 0, false, false, 0, 0)));
        assertThat(alertsOfOnlyTrip()).extracting(Alert::level).containsExactly("CAUTION");

        when(weatherService.getDailyForecasts("seoul")).thenReturn(List.of(new DailyForecast(TODAY, 20, 35, 0, false, false, 0, 0)));
        assertThat(alertsOfOnlyTrip()).extracting(Alert::level).containsExactly("DANGER");

        when(weatherService.getDailyForecasts("seoul")).thenReturn(List.of(new DailyForecast(TODAY, -10, 0, 0, false, false, 0, 0)));
        assertThat(alertsOfOnlyTrip()).extracting(Alert::level).containsExactly("CAUTION");

        when(weatherService.getDailyForecasts("seoul")).thenReturn(List.of(new DailyForecast(TODAY, -15, 0, 0, false, false, 0, 0)));
        assertThat(alertsOfOnlyTrip()).extracting(Alert::level).containsExactly("DANGER");

        // 경계 바로 아래는 알림 없음
        when(weatherService.getDailyForecasts("seoul")).thenReturn(List.of(new DailyForecast(TODAY, -9, 32, 0, false, false, 0, 0)));
        assertThat(alertsOfOnlyTrip()).isEmpty();
    }

    @Test
    void badAirGivesMaskTipAndVeryBadIsDanger() {
        givenTrip("서울 특별시", 0, 0);

        when(airQualityService.getForecast()).thenReturn(air("PM25", TODAY, "서울", "나쁨"));
        Alert caution = alertsOfOnlyTrip().get(0);
        assertThat(caution.level()).isEqualTo("CAUTION");
        assertThat(caution.kind()).isEqualTo("AIR");
        assertThat(caution.message()).contains("초미세먼지").contains("마스크").contains("선택");

        when(airQualityService.getForecast()).thenReturn(air("PM10", TODAY, "서울", "매우나쁨"));
        Alert danger = alertsOfOnlyTrip().get(0);
        assertThat(danger.level()).isEqualTo("DANGER");
        assertThat(danger.message()).contains("미세먼지").contains("매우나쁨");

        // '보통'과 다른 지역의 '나쁨'은 무시
        when(airQualityService.getForecast()).thenReturn(air("PM10", TODAY, "서울", "보통"));
        assertThat(alertsOfOnlyTrip()).isEmpty();
        when(airQualityService.getForecast()).thenReturn(air("PM10", TODAY, "부산", "나쁨"));
        assertThat(alertsOfOnlyTrip()).isEmpty();
    }

    @Test
    void warningsAreMatchedByRegionKeywordAndWarningIsDanger() {
        givenTrip("서울 특별시", 0, 1);
        when(weatherWarningService.getActiveWarnings()).thenReturn(new WeatherWarningResponse("2026-10-08T10:00", List.of(
                new Warning("호우주의보", "서울, 경기북부, 전남"),
                new Warning("태풍경보", "제주도남쪽먼바다"),
                new Warning("강풍주의보", "서해5도(백령도.대청도), 흑산도")
        )));

        List<Alert> alerts = alertsOfOnlyTrip();
        assertThat(alerts).hasSize(1);
        assertThat(alerts.get(0).kind()).isEqualTo("WARNING");
        assertThat(alerts.get(0).level()).isEqualTo("CAUTION");
        assertThat(alerts.get(0).date()).isNull();
        assertThat(alerts.get(0).message()).contains("호우주의보").contains("서울").doesNotContain("전남");

        // 경보는 위험
        givenTrip("제주도", 0, 1);
        List<Alert> jeju = alertsOfOnlyTrip();
        assertThat(jeju).extracting(Alert::level).containsExactly("DANGER");
    }

    @Test
    void dangerSortsBeforeCaution() {
        givenTrip("서울 특별시", 0, 1);
        when(weatherService.getDailyForecasts("seoul")).thenReturn(List.of(
                new DailyForecast(TODAY, 15, 22, 70, true, false, 2, 0),
                new DailyForecast(TODAY.plusDays(1), 15, 36, 0, false, false, 0, 0)
        ));
        assertThat(alertsOfOnlyTrip()).extracting(Alert::level).containsExactly("DANGER", "CAUTION");
    }

    @Test
    void onlyTripDaysInsideTheWindowAreEvaluated() {
        // 여행 3일차(오늘+2)까지만 예보 범위, 비가 오는 4일차(오늘+3)는 평가하지 않는다
        givenTrip("서울 특별시", 2, 6);
        when(weatherService.getDailyForecasts("seoul")).thenReturn(List.of(
                new DailyForecast(TODAY.plusDays(2), 15, 22, 0, false, false, 0, 0),
                new DailyForecast(TODAY.plusDays(3), 15, 22, 90, true, false, 0, 0)
        ));
        TripAlerts trip = service.getAlerts("a@test.local").trips().get(0);
        assertThat(trip.forecastAvailable()).isTrue();
        assertThat(trip.alerts()).isEmpty();

        // 여행 시작 전날의 예보(여행 아닌 날)도 평가하지 않는다
        givenTrip("서울 특별시", 1, 1);
        when(weatherService.getDailyForecasts("seoul")).thenReturn(List.of(
                new DailyForecast(TODAY, 15, 22, 90, true, false, 0, 0),
                new DailyForecast(TODAY.plusDays(1), 15, 22, 0, false, false, 0, 0)
        ));
        assertThat(alertsOfOnlyTrip()).isEmpty();
    }

    @Test
    void tripOutsideWindowReportsNoForecastAndCallsNothing() {
        givenTrip("서울 특별시", 3, 5);

        TripAlerts trip = service.getAlerts("a@test.local").trips().get(0);
        assertThat(trip.forecastAvailable()).isFalse();
        assertThat(trip.daysUntilStart()).isEqualTo(3);
        assertThat(trip.alerts()).isEmpty();
        verify(weatherService, never()).getDailyForecasts(anyString());
        verify(airQualityService, never()).getForecast();
        verify(weatherWarningService, never()).getActiveWarnings();
    }

    @Test
    void finishedTripsAreExcludedAndOngoingTripsIncluded() {
        User owner = mock(User.class);
        Trip finished = new Trip(owner, "끝난 여행", "서울 특별시", TODAY.minusDays(5), TODAY.minusDays(1), "PLANNED");
        Trip ongoing = new Trip(owner, "진행 중", "서울 특별시", TODAY.minusDays(1), TODAY.plusDays(1), "PLANNED");
        when(tripRepository.findByUser_UserIdOrderByStartDateAsc(1L)).thenReturn(List.of(finished, ongoing));

        List<TripAlerts> trips = service.getAlerts("a@test.local").trips();
        assertThat(trips).extracting(TripAlerts::title).containsExactly("진행 중");
        assertThat(trips.get(0).daysUntilStart()).isEqualTo(-1);
        assertThat(trips.get(0).forecastAvailable()).isTrue();
    }

    @Test
    void unknownRegionYieldsNoAlerts() {
        givenTrip("기타", 0, 1);
        when(weatherService.getDailyForecasts(anyString())).thenReturn(List.of(new DailyForecast(TODAY, 15, 40, 100, true, false, 99, 0)));
        assertThat(alertsOfOnlyTrip()).isEmpty();
    }

    @Test
    void regionNameIsMatchedIgnoringSpaces() {
        givenTrip("경기도/인천", 0, 0);
        when(weatherService.getDailyForecasts("gi")).thenReturn(List.of(new DailyForecast(TODAY, 15, 36, 0, false, false, 0, 0)));
        assertThat(alertsOfOnlyTrip()).hasSize(1);
    }

    @Test
    void failingSourceIsReportedAndOthersStillWork() {
        givenTrip("서울 특별시", 0, 0);
        when(airQualityService.getForecast()).thenThrow(new ResponseStatusException(org.springframework.http.HttpStatus.BAD_GATEWAY));
        when(weatherWarningService.getActiveWarnings()).thenThrow(new IllegalStateException("boom"));
        when(weatherService.getDailyForecasts("seoul")).thenReturn(List.of(new DailyForecast(TODAY, 15, 36, 0, false, false, 0, 0)));

        TripAlertsResponse response = service.getAlerts("a@test.local");
        assertThat(response.unavailableSources()).containsExactlyInAnyOrder("대기질", "기상특보");
        assertThat(response.trips().get(0).alerts()).extracting(Alert::kind).containsExactly("TEMPERATURE");
    }

    @Test
    void weatherFailureIsReportedOncePerRequest() {
        givenTrip("서울 특별시", 0, 0);
        when(weatherService.getDailyForecasts("seoul")).thenThrow(new IllegalStateException("down"));

        TripAlertsResponse response = service.getAlerts("a@test.local");
        assertThat(response.unavailableSources()).containsExactly("날씨");
        assertThat(response.trips().get(0).alerts()).isEmpty();
    }
}
