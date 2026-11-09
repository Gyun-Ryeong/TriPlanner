package com.triplanner.backend.dto;

import java.util.List;
import java.util.Map;

// 한 달치 축제. days 는 날짜(yyyy-MM-dd) → 그날 열리는 축제 contentId 목록이고, 맨 앞이 대표(나머지는 "+N")다.
// available 이 false 면 "축제가 없다"가 아니라 "정보를 불러오지 못했다"는 뜻이다 (RAG 서버 꺼짐·공공 API 장애)
public record FestivalCalendarResponse(
        String sido,
        int year,
        int month,
        List<FestivalSummary> festivals,
        Map<String, List<String>> days,
        boolean available
) {

    public static FestivalCalendarResponse unavailable(String sido, int year, int month) {
        return new FestivalCalendarResponse(sido, year, month, List.of(), Map.of(), false);
    }
}
