package com.triplanner.backend.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;
import java.time.LocalTime;

public record TripItemRequest(
        Long placeId,
        @NotBlank @Size(max = 20, message = "항목 유형은 20자 이하여야 합니다.") String itemType,
        @NotNull Integer visitOrder,
        LocalTime startTime,
        @Size(max = 255, message = "메모는 255자 이하여야 합니다.") String memo
) {
}
