package com.triplanner.backend.service;

import com.triplanner.backend.dto.KmaForecastResponse;
import com.triplanner.backend.dto.RegionWeatherResponse;
import java.time.LocalDate;
import java.time.ZoneId;
import java.time.ZonedDateTime;
import java.time.format.DateTimeFormatter;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.stream.Collectors;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientException;

@Service
public class WeatherService {

    private record RegionGrid(String id, String name, int nx, int ny) {
    }

    // 기상청 단기예보 격자 좌표 - 앱의 7개 광역 지역별 대표 도시
    private static final List<RegionGrid> REGIONS = List.of(
            new RegionGrid("seoul", "서울", 60, 127),
            new RegionGrid("gi", "인천", 55, 124),
            new RegionGrid("gangwon", "춘천", 73, 134),
            new RegionGrid("chungcheong", "대전", 67, 100),
            new RegionGrid("jeolla", "광주", 58, 74),
            new RegionGrid("gyeongsang", "부산", 98, 76),
            new RegionGrid("jeju", "제주", 52, 38)
    );

    // 단기예보 발표시각: 매일 02,05,08,11,14,17,20,23시 (발표 후 약 10분 뒤 조회 가능)
    private static final int[] BASE_HOURS = {2, 5, 8, 11, 14, 17, 20, 23};

    private final RestClient restClient = RestClient.create();

    @Value("${public-data.service-key}")
    private String serviceKey;

    public List<RegionWeatherResponse> getRegionWeather() {
        ZonedDateTime adjusted = ZonedDateTime.now(ZoneId.of("Asia/Seoul")).minusMinutes(10);
        String baseDate = computeBaseDate(adjusted);
        String baseTime = computeBaseTime(adjusted);

        return REGIONS.stream()
                .map(region -> fetchRegionWeather(region, baseDate, baseTime))
                .filter(Objects::nonNull)
                .toList();
    }

    private RegionWeatherResponse fetchRegionWeather(RegionGrid region, String baseDate, String baseTime) {
        try {
            KmaForecastResponse response = restClient.get()
                    .uri(uriBuilder -> uriBuilder
                            .scheme("http").host("apis.data.go.kr")
                            .path("/1360000/VilageFcstInfoService_2.0/getVilageFcst")
                            .queryParam("serviceKey", serviceKey)
                            .queryParam("numOfRows", 20)
                            .queryParam("pageNo", 1)
                            .queryParam("dataType", "JSON")
                            .queryParam("base_date", baseDate)
                            .queryParam("base_time", baseTime)
                            .queryParam("nx", region.nx())
                            .queryParam("ny", region.ny())
                            .build())
                    .retrieve()
                    .body(KmaForecastResponse.class);

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

            return new RegionWeatherResponse(
                    region.id(),
                    region.name(),
                    parseIntOrNull(values.get("TMP")),
                    skyStatusLabel(values.get("SKY"), values.get("PTY")),
                    parseIntOrNull(values.get("POP"))
            );
        } catch (RestClientException | NullPointerException e) {
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
