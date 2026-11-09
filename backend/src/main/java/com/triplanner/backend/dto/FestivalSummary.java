package com.triplanner.backend.dto;

// 달력에 올릴 축제 한 건 (날짜는 yyyy-MM-dd)
public record FestivalSummary(
        String contentId,
        String title,
        String addr,
        String start,
        String end,
        String image,
        String mapx,
        String mapy
) {
}
