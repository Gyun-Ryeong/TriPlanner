package com.triplanner.backend.service;

import com.triplanner.backend.common.TtlCache;
import com.triplanner.backend.domain.Trip;
import com.triplanner.backend.domain.User;
import com.triplanner.backend.dto.AirForecast;
import com.triplanner.backend.dto.DailyForecast;
import com.triplanner.backend.dto.TripAlertsResponse;
import com.triplanner.backend.dto.TripAlertsResponse.Alert;
import com.triplanner.backend.dto.TripAlertsResponse.TripAlerts;
import com.triplanner.backend.dto.WeatherWarningResponse;
import com.triplanner.backend.repository.TripRepository;
import com.triplanner.backend.repository.UserRepository;
import java.time.Duration;
import java.time.LocalDate;
import java.time.ZoneId;
import java.time.temporal.ChronoUnit;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.function.Supplier;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;

// 여행 임박 알림: 여행 일정이 예보 제공 범위(오늘 포함 3일) 안에 들어오면 날씨·대기질·기상특보로 주의/위험 알림을 만든다.
// 모두 조회 시점에 계산하므로 예보가 바뀌면 알림도 바로 바뀐다. (알림 상태를 저장하지 않는다)
@Service
public class TripAlertService {

    private static final Logger log = LoggerFactory.getLogger(TripAlertService.class);

    private static final ZoneId KST = ZoneId.of("Asia/Seoul");

    // 오늘 포함 며칠까지 예보를 제공하는지 (단기예보·에어코리아 예보통보가 모두 약 3일치)
    static final int FORECAST_DAYS = 3;

    // 응답에는 코드로 내려가고, 화면에 보이는 이름(DANGER=주의, CAUTION=참고)은 프론트에서 붙인다
    static final String CAUTION = "CAUTION";
    static final String DANGER = "DANGER";

    // ---- 알림 기준 (주의/위험) : 한곳에 모아둔 값이라 여기만 고치면 된다 ----
    private static final int RAIN_CAUTION_POP = 50;          // 강수확률 이상이면 주의
    private static final double HEAVY_RAIN_MM = 30.0;        // 시간당 강수량(mm) 이상이면 위험
    private static final double HEAVY_SNOW_CM = 5.0;         // 시간당 신적설(cm) 이상이면 위험
    private static final int HOT_CAUTION = 33;               // 일 최고기온 이상이면 주의
    private static final int HOT_DANGER = 35;                // 일 최고기온 이상이면 위험
    private static final int COLD_CAUTION = -10;             // 일 최저기온 이하이면 주의
    private static final int COLD_DANGER = -15;              // 일 최저기온 이하이면 위험

    // Trip.region(공백 제거) -> 날씨 서비스의 지역 id
    private static final Map<String, String> REGION_IDS = Map.of(
            "서울특별시", "seoul",
            "경기도/인천", "gi",
            "강원도", "gangwon",
            "충청도", "chungcheong",
            "전라도", "jeolla",
            "경상도", "gyeongsang",
            "제주도", "jeju"
    );

    // 날씨 카드의 대표 도시와 같은 기준으로 고른 에어코리아 예보 권역
    private static final Map<String, String> AIR_AREAS = Map.of(
            "seoul", "서울",
            "gi", "인천",
            "gangwon", "영서",
            "chungcheong", "대전",
            "jeolla", "광주",
            "gyeongsang", "부산",
            "jeju", "제주"
    );

    // 기상특보 지역 텍스트(전국 단위 자유 텍스트)에서 우리 지역을 찾는 키워드
    private static final Map<String, List<String>> WARNING_KEYWORDS = Map.of(
            "seoul", List.of("서울"),
            "gi", List.of("경기", "인천", "서해5도"),
            "gangwon", List.of("강원"),
            "chungcheong", List.of("충청", "충북", "충남", "대전", "세종"),
            "jeolla", List.of("전라", "전북", "전남", "광주", "흑산도"),
            "gyeongsang", List.of("경상", "경북", "경남", "부산", "대구", "울산", "울릉도", "독도"),
            "jeju", List.of("제주")
    );

    private final TripRepository tripRepository;
    private final UserRepository userRepository;
    private final WeatherService weatherService;
    private final AirQualityService airQualityService;
    private final WeatherWarningService weatherWarningService;

    private final TtlCache<String, WeatherWarningResponse> warningCache = new TtlCache<>(Duration.ofMinutes(5));

    public TripAlertService(
            TripRepository tripRepository,
            UserRepository userRepository,
            WeatherService weatherService,
            AirQualityService airQualityService,
            WeatherWarningService weatherWarningService
    ) {
        this.tripRepository = tripRepository;
        this.userRepository = userRepository;
        this.weatherService = weatherService;
        this.airQualityService = airQualityService;
        this.weatherWarningService = weatherWarningService;
    }

    public TripAlertsResponse getAlerts(String email) {
        User user = userRepository.findByEmail(email)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.UNAUTHORIZED, "사용자를 찾을 수 없습니다."));

        // 프로필에서 여행 알림을 꺼둔 사용자는 외부 API를 부르지 않고 바로 '꺼짐'으로 응답한다
        if (!user.isNotifyTripAlerts()) {
            return new TripAlertsResponse(false, List.of(), List.of());
        }

        LocalDate today = LocalDate.now(KST);
        LocalDate windowEnd = today.plusDays(FORECAST_DAYS - 1L);

        // 이미 끝난 여행은 제외한다
        List<Trip> trips = tripRepository.findByUser_UserIdOrderByStartDateAsc(user.getUserId()).stream()
                .filter(t -> t.getStartDate() != null && t.getEndDate() != null && !t.getEndDate().isBefore(today))
                .toList();

        Set<String> unavailable = new LinkedHashSet<>();
        boolean anyInWindow = trips.stream().anyMatch(t -> !t.getStartDate().isAfter(windowEnd));
        AirForecast air = anyInWindow ? load("대기질", unavailable, airQualityService::getForecast) : null;
        WeatherWarningResponse warnings = anyInWindow
                ? load("기상특보", unavailable, () -> warningCache.get("now", weatherWarningService::getActiveWarnings))
                : null;
        Map<String, List<DailyForecast>> weatherByRegion = new HashMap<>();

        List<TripAlerts> result = new ArrayList<>();
        for (Trip trip : trips) {
            boolean forecastAvailable = !trip.getStartDate().isAfter(windowEnd);
            long daysUntilStart = ChronoUnit.DAYS.between(today, trip.getStartDate());
            List<Alert> alerts = new ArrayList<>();

            String regionId = REGION_IDS.get(normalize(trip.getRegion()));
            if (forecastAvailable && regionId != null) {
                LocalDate from = trip.getStartDate().isAfter(today) ? trip.getStartDate() : today;
                LocalDate to = trip.getEndDate().isBefore(windowEnd) ? trip.getEndDate() : windowEnd;

                List<DailyForecast> forecasts = weatherByRegion.computeIfAbsent(regionId, id -> {
                    List<DailyForecast> loaded = load("날씨", unavailable, () -> weatherService.getDailyForecasts(id));
                    return loaded == null ? List.of() : loaded;
                });
                for (DailyForecast forecast : forecasts) {
                    if (!forecast.date().isBefore(from) && !forecast.date().isAfter(to)) {
                        addWeatherAlerts(alerts, forecast);
                    }
                }
                if (air != null) {
                    for (LocalDate day = from; !day.isAfter(to); day = day.plusDays(1)) {
                        addAirAlert(alerts, air, regionId, day);
                    }
                }
                if (warnings != null) {
                    addWarningAlerts(alerts, warnings, regionId);
                }
            }

            alerts.sort(Comparator
                    .comparing((Alert a) -> DANGER.equals(a.level()) ? 0 : 1)
                    .thenComparing(a -> a.date() == null ? LocalDate.MIN : a.date()));

            result.add(new TripAlerts(trip.getTripId(), trip.getTitle(), trip.getRegion(),
                    trip.getStartDate(), trip.getEndDate(), daysUntilStart, forecastAvailable, alerts));
        }

        return new TripAlertsResponse(true, result, List.copyOf(unavailable));
    }

    private void addWeatherAlerts(List<Alert> out, DailyForecast f) {
        String day = dayLabel(f.date());

        // 강수: 많은 비·눈은 위험, 비·눈 예보나 높은 강수확률은 주의
        if (f.maxHourlyRainMm() >= HEAVY_RAIN_MM) {
            out.add(new Alert(DANGER, "PRECIPITATION", f.date(),
                    day + " 시간당 " + (int) f.maxHourlyRainMm() + "mm 이상의 강한 비가 예보됐어요. 야외 일정은 실내로 바꾸는 것을 검토해 주세요."));
        } else if (f.maxHourlySnowCm() >= HEAVY_SNOW_CM) {
            out.add(new Alert(DANGER, "PRECIPITATION", f.date(),
                    day + " 시간당 " + (int) f.maxHourlySnowCm() + "cm 이상의 많은 눈이 예보됐어요. 이동과 야외 일정을 다시 확인해 주세요."));
        } else if (f.rain() || f.snow() || (f.maxPop() != null && f.maxPop() >= RAIN_CAUTION_POP)) {
            String type = f.rain() && f.snow() ? "비/눈" : f.snow() ? "눈" : f.rain() ? "비" : null;
            String pop = f.maxPop() != null ? "강수확률 " + f.maxPop() + "%" : null;
            String detail = type != null
                    ? type + " 예보예요" + (pop != null ? " (" + pop + ")" : "")
                    : pop + "예요";
            out.add(new Alert(CAUTION, "PRECIPITATION", f.date(),
                    day + " " + detail + ". 우산을 챙기고, 야외 일정은 실내 대안도 함께 생각해 보세요."));
        }

        // 기온
        if (f.maxTemp() != null && f.maxTemp() >= HOT_DANGER) {
            out.add(new Alert(DANGER, "TEMPERATURE", f.date(),
                    day + " 최고기온 " + f.maxTemp() + "°의 폭염이 예상돼요. 야외 일정은 시간대를 조정하거나 실내로 바꾸는 것을 검토해 주세요."));
        } else if (f.maxTemp() != null && f.maxTemp() >= HOT_CAUTION) {
            out.add(new Alert(CAUTION, "TEMPERATURE", f.date(),
                    day + " 최고기온 " + f.maxTemp() + "°로 많이 더워요. 물을 충분히 챙기고 한낮 야외 활동은 주의하세요."));
        }
        if (f.minTemp() != null && f.minTemp() <= COLD_DANGER) {
            out.add(new Alert(DANGER, "TEMPERATURE", f.date(),
                    day + " 최저기온 " + f.minTemp() + "°의 강한 추위가 예상돼요. 야외 일정은 실내로 바꾸는 것을 검토해 주세요."));
        } else if (f.minTemp() != null && f.minTemp() <= COLD_CAUTION) {
            out.add(new Alert(CAUTION, "TEMPERATURE", f.date(),
                    day + " 최저기온 " + f.minTemp() + "°로 매우 추워요. 방한 준비를 챙기세요."));
        }
    }

    private void addAirAlert(List<Alert> out, AirForecast air, String regionId, LocalDate date) {
        String area = AIR_AREAS.get(regionId);
        int pm10 = gradeRank(air.grade("PM10", date, area));
        int pm25 = gradeRank(air.grade("PM25", date, area));
        int worst = Math.max(pm10, pm25);
        if (worst < 2) {
            return;
        }

        String pollutant = pm10 == pm25 ? "미세먼지·초미세먼지" : pm10 > pm25 ? "미세먼지" : "초미세먼지";
        String gradeName = worst == 3 ? "매우나쁨" : "나쁨";
        String day = dayLabel(date);

        if (worst == 3) {
            out.add(new Alert(DANGER, "AIR", date,
                    day + " " + pollutant + " '" + gradeName + "' 예보예요. 가능하면 실내 활동을 권장해요. 야외에서 활동한다면 마스크를 꼭 챙기세요."));
        } else {
            out.add(new Alert(CAUTION, "AIR", date,
                    day + " " + pollutant + " '" + gradeName + "' 예보예요. 야외 활동 시 마스크를 챙기면 도움이 돼요. 일정을 바꿀지는 편한 대로 선택하세요."));
        }
    }

    // 기상특보는 "현재 발효 중"인 값이라 특정 날짜에 묶지 않는다. 경보는 위험, 주의보는 주의.
    private void addWarningAlerts(List<Alert> out, WeatherWarningResponse warnings, String regionId) {
        List<String> keywords = WARNING_KEYWORDS.getOrDefault(regionId, List.of());
        for (WeatherWarningResponse.Warning warning : warnings.warnings()) {
            List<String> matched = new ArrayList<>();
            for (String token : warning.areas().split("[,，]")) {
                String area = token.trim();
                if (!area.isEmpty() && keywords.stream().anyMatch(area::contains)) {
                    matched.add(area);
                }
            }
            if (matched.isEmpty()) {
                continue;
            }

            String where = String.join(", ", matched.subList(0, Math.min(3, matched.size())));
            String level = warning.type().contains("경보") ? DANGER : CAUTION;
            out.add(new Alert(level, "WARNING", null,
                    "현재 " + warning.type() + "가 발효 중이에요 (" + where + "). 여행 일정에 영향이 있을 수 있으니 확인해 주세요."));
        }
    }

    // 0 정보없음, 1 좋음, 1 보통(같은 취급), 2 나쁨, 3 매우나쁨
    private int gradeRank(String grade) {
        if (grade == null) {
            return 0;
        }
        return switch (grade) {
            case "나쁨" -> 2;
            case "매우나쁨" -> 3;
            default -> 1;
        };
    }

    private <T> T load(String sourceName, Set<String> unavailable, Supplier<T> loader) {
        try {
            return loader.get();
        } catch (RuntimeException e) {
            // 예외 메시지에는 서비스키가 담긴 요청 URL이 들어 있을 수 있어 클래스명만 남긴다
            log.warn("여행 알림용 {} 조회 실패: {}", sourceName, e.getClass().getSimpleName());
            unavailable.add(sourceName);
            return null;
        }
    }

    private String normalize(String region) {
        return region == null ? "" : region.replaceAll("\\s+", "");
    }

    private String dayLabel(LocalDate date) {
        return date.getMonthValue() + "월 " + date.getDayOfMonth() + "일";
    }
}
