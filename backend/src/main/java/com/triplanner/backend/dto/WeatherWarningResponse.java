package com.triplanner.backend.dto;

import java.util.List;

public record WeatherWarningResponse(String announcedAt, List<Warning> warnings) {

    public record Warning(String type, String areas) {
    }
}
