package com.triplanner.backend.dto;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import java.util.List;

@JsonIgnoreProperties(ignoreUnknown = true)
public record KmaForecastResponse(KmaResponseBody response) {

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record KmaResponseBody(KmaHeader header, KmaBody body) {
    }

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record KmaHeader(String resultCode, String resultMsg) {
    }

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record KmaBody(KmaItems items) {
    }

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record KmaItems(List<KmaItem> item) {
    }

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record KmaItem(
            String baseDate,
            String baseTime,
            String category,
            String fcstDate,
            String fcstTime,
            String fcstValue,
            Integer nx,
            Integer ny
    ) {
    }
}
