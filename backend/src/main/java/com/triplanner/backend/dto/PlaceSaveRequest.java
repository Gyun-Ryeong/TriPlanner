package com.triplanner.backend.dto;

import jakarta.validation.constraints.DecimalMax;
import jakarta.validation.constraints.DecimalMin;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

public record PlaceSaveRequest(
        @NotBlank @Size(max = 50, message = "장소 식별자는 50자 이하여야 합니다.") String contentId,
        @NotBlank @Size(max = 200, message = "장소 이름은 200자 이하여야 합니다.") String name,
        @Size(max = 50, message = "분류는 50자 이하여야 합니다.") String category,
        @Size(max = 255, message = "주소는 255자 이하여야 합니다.") String address,
        @DecimalMin(value = "-90", message = "위도 값이 올바르지 않습니다.")
        @DecimalMax(value = "90", message = "위도 값이 올바르지 않습니다.") Double latitude,
        @DecimalMin(value = "-180", message = "경도 값이 올바르지 않습니다.")
        @DecimalMax(value = "180", message = "경도 값이 올바르지 않습니다.") Double longitude
) {
}
