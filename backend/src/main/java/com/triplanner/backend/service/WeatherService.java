package com.triplanner.backend.service;

import com.triplanner.backend.common.TtlCache;
import com.triplanner.backend.dto.DailyForecast;
import com.triplanner.backend.dto.KmaForecastResponse;
import com.triplanner.backend.dto.RegionWeatherResponse;
import com.triplanner.backend.dto.RegionWeatherResponse.CityWeather;
import java.net.http.HttpClient;
import java.time.Duration;
import java.time.LocalDate;
import java.time.ZoneId;
import java.time.ZonedDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import java.util.stream.Collectors;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.http.client.JdkClientHttpRequestFactory;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientException;
import org.springframework.web.server.ResponseStatusException;

@Service
public class WeatherService {

    private record CityGrid(String name, int nx, int ny) {
    }

    // cities 의 첫 번째 도시가 대표 도시다 (여행 알림의 예보는 대표 도시 기준)
    private record RegionGrid(String id, String name, List<CityGrid> cities) {
        CityGrid representative() {
            return cities.get(0);
        }
    }

    // 앱의 7개 광역 권역(이름은 여행 만들기 화면과 동일) 아래의 주요 도시와 기상청 단기예보 격자 좌표.
    // 격자는 기상청 공식 변환식으로 계산했다 (기존 검증된 대표 도시 6곳과 일치 확인, 오차는 격자 1칸=5km 이내).
    private static final List<RegionGrid> REGIONS = List.of(
            new RegionGrid("seoul", "서울 특별시", List.of(
                    new CityGrid("서울", 60, 127))),
            new RegionGrid("gi", "경기도 / 인천", List.of(
                    new CityGrid("인천", 55, 124),
                    new CityGrid("수원", 61, 120),
                    new CityGrid("가평", 69, 133))),
            new RegionGrid("gangwon", "강원도", List.of(
                    new CityGrid("춘천", 73, 134),
                    new CityGrid("강릉", 92, 132),
                    new CityGrid("속초", 87, 141))),
            new RegionGrid("chungcheong", "충청도", List.of(
                    new CityGrid("대전", 67, 100),
                    new CityGrid("청주", 69, 107),
                    new CityGrid("천안", 62, 110),
                    new CityGrid("태안", 48, 109))),
            new RegionGrid("jeolla", "전라도", List.of(
                    new CityGrid("광주", 58, 74),
                    new CityGrid("전주", 63, 89),
                    new CityGrid("여수", 73, 66),
                    new CityGrid("목포", 50, 67))),
            new RegionGrid("gyeongsang", "경상도", List.of(
                    new CityGrid("부산", 98, 76),
                    new CityGrid("대구", 89, 91),
                    new CityGrid("울산", 102, 84),
                    new CityGrid("경주", 100, 91),
                    new CityGrid("안동", 91, 106))),
            new RegionGrid("jeju", "제주도", List.of(
                    new CityGrid("제주", 52, 38),
                    new CityGrid("서귀포", 52, 33)))
    );

    // 단기예보 발표시각: 매일 02,05,08,11,14,17,20,23시 (발표 후 약 10분 뒤 조회 가능)
    private static final int[] BASE_HOURS = {2, 5, 8, 11, 14, 17, 20, 23};

    private static final ZoneId KST = ZoneId.of("Asia/Seoul");
    private static final Pattern AMOUNT_NUMBER = Pattern.compile("\\d+(?:\\.\\d+)?");

    private static final Logger log = LoggerFactory.getLogger(WeatherService.class);

    // 도시 약 22곳을 동시에 부르므로, 느린 한 곳이 전체를 붙잡지 않게 읽기 타임아웃을 둔다
    private final RestClient restClient = RestClient.builder()
            .requestFactory(externalApiRequestFactory())
            .build();

    private final TtlCache<String, List<DailyForecast>> dailyCache = new TtlCache<>(Duration.ofMinutes(10));
    private final TtlCache<String, List<RegionWeatherResponse>> regionCache = new TtlCache<>(Duration.ofMinutes(10));

    @Value("${public-data.service-key}")
    private String serviceKey;

    private static JdkClientHttpRequestFactory externalApiRequestFactory() {
        JdkClientHttpRequestFactory factory = new JdkClientHttpRequestFactory(
                HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(3)).build());
        factory.setReadTimeout(Duration.ofSeconds(8));
        return factory;
    }

    private record LoadedRegions(List<RegionWeatherResponse> regions, boolean complete) {
    }

    // 권역별 도시 날씨 (도시 약 22곳을 병렬로 조회하고 10분 캐시한다. 일부 도시가 실패한 결과는 캐시하지 않는다)
    public List<RegionWeatherResponse> getRegionWeather() {
        List<RegionWeatherResponse> cached = regionCache.getIfPresent("regions");
        if (cached != null) {
            return cached;
        }
        LoadedRegions loaded = fetchAllRegionWeather();
        if (loaded.complete()) {
            regionCache.put("regions", loaded.regions());
        }
        return loaded.regions();
    }

    private LoadedRegions fetchAllRegionWeather() {
        ZonedDateTime adjusted = ZonedDateTime.now(KST).minusMinutes(10);
        String baseDate = computeBaseDate(adjusted);
        String baseTime = computeBaseTime(adjusted);

        boolean complete = true;
        List<RegionWeatherResponse> result = new ArrayList<>();
        try (ExecutorService executor = Executors.newVirtualThreadPerTaskExecutor()) {
            Map<RegionGrid, List<Future<CityWeather>>> futures = new LinkedHashMap<>();
            for (RegionGrid region : REGIONS) {
                futures.put(region, region.cities().stream()
                        .map(city -> executor.submit(() -> fetchCityWeather(city, baseDate, baseTime)))
                        .toList());
            }

            for (Map.Entry<RegionGrid, List<Future<CityWeather>>> entry : futures.entrySet()) {
                List<CityWeather> cities = new ArrayList<>();
                for (Future<CityWeather> future : entry.getValue()) {
                    CityWeather city = awaitOrNull(future);
                    if (city != null) {
                        cities.add(city);
                    } else {
                        complete = false;
                    }
                }
                if (!cities.isEmpty()) {
                    result.add(new RegionWeatherResponse(entry.getKey().id(), entry.getKey().name(), cities));
                }
            }
        }

        if (result.isEmpty()) {
            throw new ResponseStatusException(HttpStatus.BAD_GATEWAY, "기상청 서버에서 날씨 정보를 불러오지 못했습니다.");
        }
        return new LoadedRegions(result, complete);
    }

    private CityWeather awaitOrNull(Future<CityWeather> future) {
        try {
            return future.get();
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            return null;
        } catch (ExecutionException e) {
            return null;
        }
    }

    // 여행 알림용: 지역의 앞으로 약 3일치 예보를 날짜별로 요약한다 (10분 캐시)
    public List<DailyForecast> getDailyForecasts(String regionId) {
        RegionGrid region = REGIONS.stream().filter(r -> r.id().equals(regionId)).findFirst().orElse(null);
        if (region == null) {
            return List.of();
        }
        return dailyCache.get(regionId, () -> fetchDailyForecasts(region));
    }

    private List<DailyForecast> fetchDailyForecasts(RegionGrid region) {
        ZonedDateTime adjusted = ZonedDateTime.now(KST).minusMinutes(10);
        List<KmaForecastResponse.KmaItem> items;
        try {
            // 시간별 12개 항목 x 약 3일치 = 900행 안팎
            items = requestForecast(region.representative(), computeBaseDate(adjusted), computeBaseTime(adjusted), 1500)
                    .response().body().items().item();
        } catch (RestClientException | NullPointerException e) {
            throw new IllegalStateException("기상청 단기예보를 불러오지 못했습니다.");
        }

        Map<String, List<KmaForecastResponse.KmaItem>> byDate = items.stream()
                .collect(Collectors.groupingBy(KmaForecastResponse.KmaItem::fcstDate, LinkedHashMap::new, Collectors.toList()));

        List<DailyForecast> result = new ArrayList<>();
        byDate.forEach((fcstDate, dayItems) -> result.add(summarizeDay(fcstDate, dayItems)));
        return result;
    }

    private DailyForecast summarizeDay(String fcstDate, List<KmaForecastResponse.KmaItem> dayItems) {
        Integer minTemp = null;
        Integer maxTemp = null;
        Integer maxPop = null;
        boolean rain = false;
        boolean snow = false;
        double maxRainMm = 0;
        double maxSnowCm = 0;

        for (KmaForecastResponse.KmaItem item : dayItems) {
            String value = item.fcstValue();
            switch (item.category()) {
                case "TMP" -> {
                    Integer t = parseIntOrNull(value);
                    if (t != null) {
                        minTemp = minTemp == null ? t : Math.min(minTemp, t);
                        maxTemp = maxTemp == null ? t : Math.max(maxTemp, t);
                    }
                }
                case "POP" -> {
                    Integer p = parseIntOrNull(value);
                    if (p != null) {
                        maxPop = maxPop == null ? p : Math.max(maxPop, p);
                    }
                }
                // 강수형태: 1 비, 2 비/눈, 3 눈, 4 소나기
                case "PTY" -> {
                    if ("1".equals(value) || "2".equals(value) || "4".equals(value)) {
                        rain = true;
                    }
                    if ("2".equals(value) || "3".equals(value)) {
                        snow = true;
                    }
                }
                case "PCP" -> maxRainMm = Math.max(maxRainMm, parseAmount(value));
                case "SNO" -> maxSnowCm = Math.max(maxSnowCm, parseAmount(value));
                default -> { }
            }
        }

        return new DailyForecast(LocalDate.parse(fcstDate, DateTimeFormatter.BASIC_ISO_DATE),
                minTemp, maxTemp, maxPop, rain, snow, maxRainMm, maxSnowCm);
    }

    // PCP/SNO 값: "강수없음", "1.0mm 미만", "30.0~50.0mm", "50.0mm 이상" -> 하한값(없음/미만은 0)
    private double parseAmount(String value) {
        if (value == null || value.contains("없음") || value.contains("미만")) {
            return 0;
        }
        Matcher matcher = AMOUNT_NUMBER.matcher(value);
        return matcher.find() ? Double.parseDouble(matcher.group()) : 0;
    }

    private KmaForecastResponse requestForecast(CityGrid region, String baseDate, String baseTime, int numOfRows) {
        return restClient.get()
                .uri(uriBuilder -> uriBuilder
                        .scheme("http").host("apis.data.go.kr")
                        .path("/1360000/VilageFcstInfoService_2.0/getVilageFcst")
                        .queryParam("serviceKey", serviceKey)
                        .queryParam("numOfRows", numOfRows)
                        .queryParam("pageNo", 1)
                        .queryParam("dataType", "JSON")
                        .queryParam("base_date", baseDate)
                        .queryParam("base_time", baseTime)
                        .queryParam("nx", region.nx())
                        .queryParam("ny", region.ny())
                        .build())
                .retrieve()
                .body(KmaForecastResponse.class);
    }

    private CityWeather fetchCityWeather(CityGrid city, String baseDate, String baseTime) {
        try {
            KmaForecastResponse response = requestForecast(city, baseDate, baseTime, 20);

            List<KmaForecastResponse.KmaItem> items = response.response().body().items().item();
            if (items.isEmpty()) {
                return null;
            }

            String nearestFcstTime = items.get(0).fcstTime();
            Map<String, String> values = items.stream()
                    .filter(item -> nearestFcstTime.equals(item.fcstTime()))
                    .collect(Collectors.toMap(
                            KmaForecastResponse.KmaItem::category,
                            KmaForecastResponse.KmaItem::fcstValue,
                            (a, b) -> a
                    ));

            return new CityWeather(
                    city.name(),
                    parseIntOrNull(values.get("TMP")),
                    skyStatusLabel(values.get("SKY"), values.get("PTY")),
                    parseIntOrNull(values.get("POP"))
            );
        } catch (RestClientException | NullPointerException e) {
            // 예외 메시지에는 서비스 키가 든 URL이 들어 있을 수 있어 클래스 이름만 남긴다
            log.warn("도시 날씨 조회 실패 city={} cause={}", city.name(), e.getClass().getSimpleName());
            return null;
        }
    }

    private String skyStatusLabel(String sky, String pty) {
        if (pty != null) {
            switch (pty) {
                case "1": return "비";
                case "2": return "비/눈";
                case "3": return "눈";
                case "4": return "소나기";
                default: break;
            }
        }
        if (sky != null) {
            switch (sky) {
                case "1": return "맑음";
                case "3": return "구름많음";
                case "4": return "흐림";
                default: break;
            }
        }
        return "정보 없음";
    }

    private Integer parseIntOrNull(String value) {
        try {
            return value == null ? null : Integer.parseInt(value);
        } catch (NumberFormatException e) {
            return null;
        }
    }

    private String computeBaseDate(ZonedDateTime adjusted) {
        LocalDate date = adjusted.toLocalDate();
        if (adjusted.getHour() < BASE_HOURS[0]) {
            date = date.minusDays(1);
        }
        return date.format(DateTimeFormatter.ofPattern("yyyyMMdd"));
    }

    private String computeBaseTime(ZonedDateTime adjusted) {
        int hour = adjusted.getHour();

        if (hour < BASE_HOURS[0]) {
            return String.format("%02d00", BASE_HOURS[BASE_HOURS.length - 1]);
        }

        int chosen = BASE_HOURS[0];
        for (int baseHour : BASE_HOURS) {
            if (baseHour <= hour) {
                chosen = baseHour;
            }
        }

        return String.format("%02d00", chosen);
    }
}
