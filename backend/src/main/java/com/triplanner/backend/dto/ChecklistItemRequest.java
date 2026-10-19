package com.triplanner.backend.dto;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;

public record ChecklistItemRequest(
        @NotBlank(message = "할 일 내용을 입력해 주세요.")
        @Size(max = 100, message = "내용은 100자 이하로 입력해 주세요.")
        String content,

        @NotNull(message = "기한을 선택해 주세요.")
        @Min(value = 0, message = "기한은 출발일 이전이어야 합니다.")
        @Max(value = 30, message = "기한은 출발 30일 전까지 지정할 수 있습니다.")
        Integer dueOffsetDays
) {
}
