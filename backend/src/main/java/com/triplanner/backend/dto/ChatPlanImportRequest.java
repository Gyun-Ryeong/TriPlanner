package com.triplanner.backend.dto;

import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotEmpty;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;
import java.time.LocalDate;
import java.time.LocalTime;
import java.util.List;

// 챗봇(rag_project)이 만든 일정을 '내 여행'으로 저장하는 요청
public record ChatPlanImportRequest(
        @NotBlank @Size(max = 100, message = "여행 이름은 100자 이하여야 합니다.") String title,
        // 챗봇의 시도명 (예: 부산, 경기). 앱의 권역(경상도 등)으로 바꿔 저장한다
        @NotBlank String sido,
        @NotNull LocalDate startDate,
        @NotNull LocalDate endDate,
        @NotEmpty @Size(max = 31, message = "한 번에 31일까지 저장할 수 있습니다.") List<@Valid Day> days
) {

    public record Day(
            @NotNull LocalDate date,
            @Size(max = 30, message = "하루 일정은 30개까지 저장할 수 있습니다.") List<@Valid Item> items
    ) {
    }

    // place 가 없으면 장소 없는 메모 항목으로 저장한다
    public record Item(
            @NotBlank @Size(max = 20, message = "항목 유형은 20자 이하여야 합니다.") String itemType,
            LocalTime startTime,
            @Size(max = 255, message = "메모는 255자 이하여야 합니다.") String memo,
            @Valid PlaceInfo place
    ) {
    }

    public record PlaceInfo(
            @NotBlank @Size(max = 50) String contentId,
            @NotBlank @Size(max = 200) String name,
            @Size(max = 50) String category,
            @Size(max = 255) String address,
            Double latitude,
            Double longitude
    ) {
    }
}
