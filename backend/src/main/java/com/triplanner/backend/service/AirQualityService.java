package com.triplanner.backend.service;

import com.triplanner.backend.common.TtlCache;
import com.triplanner.backend.dto.AirForecast;
import com.triplanner.backend.dto.RegionAirQualityResponse;
import com.triplanner.backend.dto.RegionAirQualityResponse.AreaAirQuality;
import com.triplanner.backend.dto.RegionAirQualityResponse.Metric;
import java.net.http.HttpClient;
import java.time.Duration;
import java.time.Instant;
import java.time.LocalDate;
import java.time.ZoneId;
import java.time.format.DateTimeParseException;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.atomic.AtomicReference;
import java.util.function.Function;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.http.client.JdkClientHttpRequestFactory;
import org.springframework.stereotype.Service;
import org.springframework.web.client.HttpClientErrorException;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientException;
import org.springframework.web.server.ResponseStatusException;
import tools.jackson.databind.JsonNode;

@Service
public class AirQualityService {

    // 7개 광역 권역(이름은 여행 만들기 화면과 동일)과 권역에 속한 시도.
    // 측정소 목록 API가 미승인이라 시도 단위(시도 내 측정소 평균)까지만 보여준다.
    private record Region(String id, String name, List<String> sidoNames) {
    }

    private static final List<Region> REGIONS = List.of(
            new Region("seoul", "서울 특별시", List.of("서울")),
            new Region("gi", "경기도 / 인천", List.of("경기", "인천")),
            new Region("gangwon", "강원도", List.of("강원")),
            new Region("chungcheong", "충청도", List.of("대전", "세종", "충북", "충남")),
            new Region("jeolla", "전라도", List.of("광주", "전북", "전남")),
            new Region("gyeongsang", "경상도", List.of("부산", "대구", "울산", "경북", "경남")),
            new Region("jeju", "제주도", List.of("제주"))
    );

    private static final String NORMAL_CODE = "00";

    private static final String DISABLED_MESSAGE = "대기질 조회는 개발 중이라 잠시 꺼 두었어요. 나중에 다시 확인해 주세요.";

    private static final String[] GRADES = {"좋음", "보통", "나쁨", "매우나쁨"};

    // 환경부 4단계 기준: 각 값 이하이면 해당 등급 (마지막 등급은 그 초과)
    private static final double[] PM10_LIMITS = {30, 80, 150};
    private static final double[] PM25_LIMITS = {15, 35, 75};
    private static final double[] O3_LIMITS = {0.030, 0.090, 0.150};
    private static final double[] KHAI_LIMITS = {50, 100, 250};

    private static final ZoneId KST = ZoneId.of("Asia/Seoul");

    // 예보통보 항목: 미세먼지, 초미세먼지만 사용 (오존은 마스크로 막을 수 없어 알림에서 제외)
    private static final Set<String> FORECAST_CODES = Set.of("PM10", "PM25");

    private static final Logger log = LoggerFactory.getLogger(AirQualityService.class);

    // 시도 17곳을 동시에 부르므로, 느린 한 곳이 전체를 붙잡지 않게 읽기 타임아웃을 둔다
    // (에어코리아는 가끔 한 시도가 10초 넘게 걸린다)
    private final RestClient restClient = RestClient.builder()
            .requestFactory(externalApiRequestFactory())
            .build();

    private final TtlCache<String, AirForecast> forecastCache = new TtlCache<>(Duration.ofMinutes(30));
    // 에어코리아 측정값은 1시간마다 갱신되므로 모든 시도를 받아온 결과는 30분 동안 다시 부르지 않는다.
    // 일부 시도만 받아온 결과는 짧게(2분) 들고 있어, 새로고침할 때마다 17곳을 다시 부르지 않게 한다
    private final TtlCache<String, List<RegionAirQualityResponse>> currentCache = new TtlCache<>(Duration.ofMinutes(30));
    private final TtlCache<String, List<RegionAirQualityResponse>> partialCache = new TtlCache<>(Duration.ofMinutes(2));

    // 마지막으로 모든 시도를 받아온 결과 (새로 받아오지 못할 때 대신 보여준다. 값의 측정 시각이 그대로 표시된다)
    private volatile List<RegionAirQualityResponse> lastComplete;

    // 호출 한도를 초과하면 이 시각까지 에어코리아를 다시 부르지 않는다 (한도를 더 소모하지 않으려고)
    private volatile Instant blockedUntil = Instant.EPOCH;
    private volatile boolean blockedByDailyQuota;

    // 에어코리아의 호출 한도 초과 응답 (HTTP 429, 또는 resultCode 22 '일일 서비스 요청제한 횟수 초과')
    static class QuotaExceededException extends RuntimeException {
        private final boolean daily;

        QuotaExceededException(boolean daily) {
            super("에어코리아 호출 한도 초과", null, false, false);
            this.daily = daily;
        }

        boolean isDaily() {
            return daily;
        }
    }

    @Value("${public-data.service-key}")
    private String serviceKey;

    // 개발 중 에어코리아 호출 횟수 한도를 아끼려고 application.yml 의 air-quality.enabled 로 호출을 통째로 막는다.
    // (설정이 없는 환경·테스트에서는 켜진 상태)
    @Value("${air-quality.enabled:true}")
    private boolean enabled = true;

    private static JdkClientHttpRequestFactory externalApiRequestFactory() {
        JdkClientHttpRequestFactory factory = new JdkClientHttpRequestFactory(
                HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(3)).build());
        factory.setReadTimeout(Duration.ofSeconds(8));
        return factory;
    }

    private record LoadedRegions(List<RegionAirQualityResponse> regions, boolean complete) {
    }

    // 권역별 대기질 (시도 17곳을 병렬로 조회한다). 새로 받아오지 못하면 마지막으로 성공한 결과를 대신 돌려주고,
    // 그런 결과도 없으면 실패 이유를 알리는 예외를 던진다
    public List<RegionAirQualityResponse> getRegionAirQuality() {
        if (!enabled) {
            throw new ResponseStatusException(HttpStatus.SERVICE_UNAVAILABLE, DISABLED_MESSAGE);
        }
        List<RegionAirQualityResponse> cached = currentCache.getIfPresent("current");
        if (cached == null) {
            cached = partialCache.getIfPresent("current");
        }
        if (cached != null) {
            return cached;
        }

        if (Instant.now().isBefore(blockedUntil)) {
            return lastCompleteOrThrow(quotaException(blockedByDailyQuota));
        }

        LoadedRegions loaded;
        try {
            loaded = fetchAllRegionAirQuality();
        } catch (ResponseStatusException e) {
            return lastCompleteOrThrow(e);
        }
        if (loaded.complete()) {
            currentCache.put("current", loaded.regions());
            lastComplete = loaded.regions();
        } else {
            partialCache.put("current", loaded.regions());
        }
        return loaded.regions();
    }

    private List<RegionAirQualityResponse> lastCompleteOrThrow(ResponseStatusException failure) {
        List<RegionAirQualityResponse> stale = lastComplete;
        if (stale != null) {
            return stale;
        }
        throw failure;
    }

    private ResponseStatusException quotaException(boolean daily) {
        return new ResponseStatusException(HttpStatus.SERVICE_UNAVAILABLE, daily
                ? "오늘 에어코리아 호출 한도를 초과했어요. 내일 다시 확인할 수 있어요."
                : "에어코리아 호출이 잠시 몰렸어요. 잠시 뒤 다시 확인해 주세요.");
    }

    // 일일 한도 초과는 자정(한도가 초기화되는 시각)까지, 그 밖의 호출 제한은 1분 동안 호출을 멈춘다
    private void blockCalls(boolean daily) {
        blockedByDailyQuota = daily;
        blockedUntil = daily
                ? LocalDate.now(KST).plusDays(1).atStartOfDay(KST).plusMinutes(5).toInstant()
                : Instant.now().plusSeconds(60);
    }

    private LoadedRegions fetchAllRegionAirQuality() {
        boolean complete = true;
        List<RegionAirQualityResponse> result = new ArrayList<>();
        AtomicReference<QuotaExceededException> quota = new AtomicReference<>();
        try (ExecutorService executor = Executors.newVirtualThreadPerTaskExecutor()) {
            Map<Region, List<Future<AreaAirQuality>>> futures = new LinkedHashMap<>();
            for (Region region : REGIONS) {
                futures.put(region, region.sidoNames().stream()
                        .map(sido -> executor.submit(() -> fetchAreaOrRecordQuota(sido, quota)))
                        .toList());
            }

            for (Map.Entry<Region, List<Future<AreaAirQuality>>> entry : futures.entrySet()) {
                List<AreaAirQuality> areas = new ArrayList<>();
                for (Future<AreaAirQuality> future : entry.getValue()) {
                    AreaAirQuality area = awaitOrNull(future);
                    if (area != null) {
                        areas.add(area);
                    } else {
                        complete = false;
                    }
                }
                if (!areas.isEmpty()) {
                    result.add(toRegion(entry.getKey(), areas));
                }
            }
        }

        QuotaExceededException quotaHit = quota.get();
        if (quotaHit != null) {
            blockCalls(quotaHit.isDaily());
        }
        if (result.isEmpty()) {
            if (quotaHit != null) {
                throw quotaException(quotaHit.isDaily());
            }
            throw new ResponseStatusException(HttpStatus.BAD_GATEWAY, "에어코리아 서버에서 대기질 정보를 불러오지 못했습니다.");
        }
        return new LoadedRegions(result, complete);
    }

    // 한도 초과는 재시도해도 소용없고 한도만 더 쓰므로, 기록만 하고 이 시도는 건너뛴다
    private AreaAirQuality fetchAreaOrRecordQuota(String sidoName, AtomicReference<QuotaExceededException> quota) {
        try {
            return fetchAreaWithRetry(sidoName);
        } catch (QuotaExceededException e) {
            quota.compareAndSet(null, e);
            return null;
        }
    }

    private AreaAirQuality awaitOrNull(Future<AreaAirQuality> future) {
        try {
            return future.get();
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            return null;
        } catch (ExecutionException e) {
            return null;
        }
    }

    // 권역 값 = 권역 안 시도 중 가장 나쁜(높은) 값. 시도가 둘 이상일 때만 어느 시도 값인지 함께 내려준다.
    private RegionAirQualityResponse toRegion(Region region, List<AreaAirQuality> areas) {
        boolean labelArea = areas.size() > 1;
        String latestDataTime = areas.stream()
                .map(AreaAirQuality::dataTime)
                .filter(Objects::nonNull)
                .max(String::compareTo)
                .orElse(null);

        return new RegionAirQualityResponse(
                region.id(),
                region.name(),
                latestDataTime,
                worst(areas, AreaAirQuality::pm10, labelArea),
                worst(areas, AreaAirQuality::pm25, labelArea),
                worst(areas, AreaAirQuality::o3, labelArea),
                worst(areas, AreaAirQuality::khai, labelArea),
                areas
        );
    }

    private Metric worst(List<AreaAirQuality> areas, Function<AreaAirQuality, Metric> getter, boolean labelArea) {
        AreaAirQuality worstArea = null;
        for (AreaAirQuality area : areas) {
            Metric metric = getter.apply(area);
            if (metric == null || metric.value() == null) {
                continue;
            }
            if (worstArea == null || metric.value() > getter.apply(worstArea).value()) {
                worstArea = area;
            }
        }
        if (worstArea == null) {
            return new Metric(null, null, null);
        }
        Metric picked = getter.apply(worstArea);
        return new Metric(picked.value(), picked.grade(), labelArea ? worstArea.areaName() : null);
    }

    // 에어코리아는 가끔 한 시도의 응답이 늦어 타임아웃이 나므로 실패하면 한 번 더 시도한다
    private AreaAirQuality fetchAreaWithRetry(String sidoName) {
        AreaAirQuality area = fetchAreaAirQuality(sidoName);
        return area != null ? area : fetchAreaAirQuality(sidoName);
    }

    // 에어코리아 시도별 실시간 측정정보(getCtprvnRltmMesureDnsty): 시도 내 모든 측정소 값을 평균 낸다
    AreaAirQuality fetchAreaAirQuality(String sidoName) {
        try {
            JsonNode root = restClient.get()
                    .uri(uriBuilder -> uriBuilder
                            .scheme("https").host("apis.data.go.kr")
                            .path("/B552584/ArpltnInforInqireSvc/getCtprvnRltmMesureDnsty")
                            .queryParam("serviceKey", serviceKey)
                            .queryParam("sidoName", sidoName)
                            .queryParam("ver", "1.0")
                            .queryParam("returnType", "json")
                            .queryParam("numOfRows", 200)
                            .queryParam("pageNo", 1)
                            .build())
                    .retrieve()
                    .body(JsonNode.class);

            // 한도 초과가 HTTP 200 으로 오는 경우도 있다
            if (root != null && isDailyQuotaBody(root.path("OpenAPI_ServiceResponse").path("cmmMsgHeader").path("returnReasonCode").asText())) {
                log.warn("대기질 조회 실패 sido={} cause=일일 호출 한도 초과", sidoName);
                throw new QuotaExceededException(true);
            }
            if (root == null || !NORMAL_CODE.equals(root.path("response").path("header").path("resultCode").asText())) {
                log.warn("대기질 조회 실패 sido={} cause=비정상 응답 코드", sidoName);
                return null;
            }

            JsonNode items = root.path("response").path("body").path("items");
            if (!items.isArray() || items.isEmpty()) {
                log.warn("대기질 조회 실패 sido={} cause=측정소 데이터 없음", sidoName);
                return null;
            }

            String latestDataTime = null;
            for (JsonNode item : items) {
                String dataTime = item.path("dataTime").asText(null);
                if (dataTime != null && (latestDataTime == null || dataTime.compareTo(latestDataTime) > 0)) {
                    latestDataTime = dataTime;
                }
            }

            return new AreaAirQuality(
                    sidoName,
                    latestDataTime,
                    metric(items, "pm10Value", PM10_LIMITS, 0),
                    metric(items, "pm25Value", PM25_LIMITS, 0),
                    metric(items, "o3Value", O3_LIMITS, 3),
                    metric(items, "khaiValue", KHAI_LIMITS, 0)
            );
        } catch (HttpClientErrorException.TooManyRequests e) {
            // 에러 본문에 resultCode 22(일일 서비스 요청제한 횟수 초과)가 있으면 자정까지, 아니면 잠깐만 호출을 멈춘다
            boolean daily = isDailyQuotaBody(e.getResponseBodyAsString());
            log.warn("대기질 조회 실패 sido={} cause=호출 한도 초과 daily={}", sidoName, daily);
            throw new QuotaExceededException(daily);
        } catch (RestClientException e) {
            // 예외 메시지에는 서비스 키가 든 URL이 들어 있을 수 있어 클래스 이름만 남긴다
            log.warn("대기질 조회 실패 sido={} cause={}", sidoName, e.getClass().getSimpleName());
            return null;
        }
    }

    // 에어코리아의 '일일 서비스 요청제한 횟수 초과' 표시 (returnReasonCode 22 / LIMITED_NUMBER_OF_SERVICE_REQUESTS_EXCEEDS_ERROR)
    private static boolean isDailyQuotaBody(String text) {
        return text != null
                && (text.contains("LIMITED_NUMBER_OF_SERVICE_REQUESTS_EXCEEDS_ERROR")
                || text.matches("(?s).*\"returnReasonCode\"\\s*:\\s*\"22\".*")
                || "22".equals(text.trim()));
    }

    // 여행 알림용: 미세먼지(PM10)/초미세먼지(PM25) 예보통보(getMinuDustFrcstDspth)에서 날짜별 최신 발표분의 권역 등급을 모은다 (30분 캐시)
    public AirForecast getForecast() {
        if (!enabled) {
            // 막아 둔 동안은 예보가 없는 것으로 취급해, 여행 알림에 '대기질을 불러오지 못했다'는 문구가 매번 붙지 않게 한다
            return new AirForecast(Map.of());
        }
        return forecastCache.get("forecast", this::fetchForecast);
    }

    private AirForecast fetchForecast() {
        LocalDate today = LocalDate.now(KST);
        JsonNode items = fetchForecastItems(today);
        if (items == null || !items.isArray() || items.isEmpty()) {
            // 새벽에는 오늘자 발표가 아직 없을 수 있어 전날 발표분(오늘·내일·모레 포함)으로 대신한다
            items = fetchForecastItems(today.minusDays(1));
        }
        if (items == null || !items.isArray() || items.isEmpty()) {
            throw new ResponseStatusException(HttpStatus.BAD_GATEWAY, "에어코리아 서버에서 대기질 예보를 불러오지 못했습니다.");
        }

        // (항목, 예보일)마다 발표시각("2026-10-08 17시 발표")이 가장 늦은 것만 사용한다
        Map<String, JsonNode> latest = new HashMap<>();
        for (JsonNode item : items) {
            String code = item.path("informCode").asText();
            String informDate = item.path("informData").asText();
            if (!FORECAST_CODES.contains(code) || informDate.isEmpty()) {
                continue;
            }
            String key = code + "|" + informDate;
            JsonNode current = latest.get(key);
            if (current == null || item.path("dataTime").asText().compareTo(current.path("dataTime").asText()) > 0) {
                latest.put(key, item);
            }
        }

        Map<String, Map<LocalDate, Map<String, String>>> grades = new HashMap<>();
        for (JsonNode item : latest.values()) {
            try {
                LocalDate date = LocalDate.parse(item.path("informData").asText());
                grades.computeIfAbsent(item.path("informCode").asText(), k -> new HashMap<>())
                        .put(date, parseAreaGrades(item.path("informGrade").asText("")));
            } catch (DateTimeParseException e) {
                // 날짜 형식이 다른 행은 건너뛴다
            }
        }
        return new AirForecast(grades);
    }

    private JsonNode fetchForecastItems(LocalDate searchDate) {
        try {
            JsonNode root = restClient.get()
                    .uri(uriBuilder -> uriBuilder
                            .scheme("https").host("apis.data.go.kr")
                            .path("/B552584/ArpltnInforInqireSvc/getMinuDustFrcstDspth")
                            .queryParam("serviceKey", serviceKey)
                            .queryParam("returnType", "json")
                            .queryParam("numOfRows", 100)
                            .queryParam("pageNo", 1)
                            .queryParam("searchDate", searchDate.toString())
                            .build())
                    .retrieve()
                    .body(JsonNode.class);

            if (root == null || !NORMAL_CODE.equals(root.path("response").path("header").path("resultCode").asText())) {
                return null;
            }
            return root.path("response").path("body").path("items");
        } catch (RestClientException e) {
            return null;
        }
    }

    // informGrade 형식: "서울 : 좋음,제주 : 보통,경기남부 : 나쁨,..."
    private Map<String, String> parseAreaGrades(String text) {
        Map<String, String> result = new HashMap<>();
        for (String part : text.split(",")) {
            int sep = part.indexOf(':');
            if (sep > 0) {
                result.put(part.substring(0, sep).trim(), part.substring(sep + 1).trim());
            }
        }
        return result;
    }

    private Metric metric(JsonNode items, String field, double[] limits, int decimals) {
        double sum = 0;
        int count = 0;
        for (JsonNode item : items) {
            Double value = parseOrNull(item.path(field).asText(null));
            if (value != null) {
                sum += value;
                count++;
            }
        }
        if (count == 0) {
            return new Metric(null, null, null);
        }

        double scale = Math.pow(10, decimals);
        double average = Math.round(sum / count * scale) / scale;
        return new Metric(average, grade(average, limits), null);
    }

    private String grade(double value, double[] limits) {
        for (int i = 0; i < limits.length; i++) {
            if (value <= limits[i]) {
                return GRADES[i];
            }
        }
        return GRADES[GRADES.length - 1];
    }

    // 점검/교정 중인 측정소는 "-" 또는 null로 내려온다
    private Double parseOrNull(String value) {
        if (value == null) {
            return null;
        }
        try {
            return Double.valueOf(value.trim());
        } catch (NumberFormatException e) {
            return null;
        }
    }
}
