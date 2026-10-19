package com.triplanner.backend.dto;

import jakarta.validation.constraints.NotNull;

public record ChecklistCheckRequest(@NotNull(message = "체크 값이 필요합니다.") Boolean checked) {
}
