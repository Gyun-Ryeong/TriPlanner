package com.triplanner.backend.dto;

import java.time.LocalDate;
import java.util.List;

// 공유 링크로 누구나 볼 수 있는 여행. 주인의 이메일·체크리스트·알림 같은 개인 정보는 담지 않는다
public record SharedTripResponse(
        String title,
        String region,
        String city,
        LocalDate startDate,
        LocalDate endDate,
        String ownerNickname,
        List<TripDayResponse> days
) {
}
