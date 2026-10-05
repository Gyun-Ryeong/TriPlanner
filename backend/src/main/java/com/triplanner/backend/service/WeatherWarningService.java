package com.triplanner.backend.service;

import com.triplanner.backend.dto.WeatherWarningResponse;
import com.triplanner.backend.dto.WeatherWarningResponse.Warning;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.time.format.DateTimeParseException;
import java.util.ArrayList;
import java.util.List;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientException;
import org.springframework.web.server.ResponseStatusException;
import tools.jackson.databind.JsonNode;

@Service
public class WeatherWarningService {

    private static final DateTimeFormatter KMA_TIME = DateTimeFormatter.ofPattern("yyyyMMddHHmm");
    private static final String NORMAL_CODE = "00";
    private static final String NO_DATA_CODE = "03";

    private final RestClient restClient = RestClient.create();

    @Value("${public-data.service-key}")
    private String serviceKey;

    // 기상청 기상특보 현황(getPwnStatus): 가장 최근 발표 기준으로 현재 발효 중인 특보를 종류별로 돌려준다
    public WeatherWarningResponse getActiveWarnings() {
        JsonNode root;
        try {
            root = restClient.get()
                    .uri(uriBuilder -> uriBuilder
                            .scheme("https").host("apis.data.go.kr")
                            .path("/1360000/WthrWrnInfoService/getPwnStatus")
                            .queryParam("serviceKey", serviceKey)
                            .queryParam("dataType", "JSON")
                            .queryParam("numOfRows", 1)
                            .queryParam("pageNo", 1)
                            .build())
                    .retrieve()
                    .body(JsonNode.class);
        } catch (RestClientException e) {
            throw unavailable();
        }

        String resultCode = root == null ? "" : root.path("response").path("header").path("resultCode").asText();
        if (NO_DATA_CODE.equals(resultCode)) {
            return new WeatherWarningResponse(null, List.of());
        }
        if (!NORMAL_CODE.equals(resultCode)) {
            throw unavailable();
        }

        JsonNode item = root.path("response").path("body").path("items").path("item").path(0);
        if (item.isMissingNode()) {
            return new WeatherWarningResponse(null, List.of());
        }

        return new WeatherWarningResponse(
                parseAnnouncedAt(item.path("tmFc").asText()),
                parseWarnings(item.path("t6").asText(""))
        );
    }

    // t6 형식: "o 강풍주의보 : 서해5도(백령도.대청도), 흑산도\r\no 풍랑주의보 : ..." (발효 특보가 없으면 "o 없음")
    private List<Warning> parseWarnings(String text) {
        List<Warning> warnings = new ArrayList<>();
        String type = null;
        StringBuilder areas = new StringBuilder();

        for (String rawLine : text.split("\\r?\\n")) {
            String line = rawLine.trim();
            if (line.isEmpty()) {
                continue;
            }
            if (line.startsWith("o ") && line.contains(" : ")) {
                if (type != null) {
                    warnings.add(new Warning(type, areas.toString().trim()));
                }
                int sep = line.indexOf(" : ");
                type = line.substring(2, sep).trim();
                areas = new StringBuilder(line.substring(sep + 3).trim());
            } else if (type != null && !line.startsWith("o ")) {
                areas.append(' ').append(line);
            }
        }
        if (type != null) {
            warnings.add(new Warning(type, areas.toString().trim()));
        }
        return warnings;
    }

    private String parseAnnouncedAt(String tmFc) {
        try {
            return LocalDateTime.parse(tmFc, KMA_TIME).toString();
        } catch (DateTimeParseException e) {
            return null;
        }
    }

    private ResponseStatusException unavailable() {
        return new ResponseStatusException(HttpStatus.BAD_GATEWAY, "기상청 서버에서 기상특보를 불러오지 못했습니다.");
    }
}
