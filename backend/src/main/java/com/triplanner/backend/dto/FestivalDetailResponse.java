package com.triplanner.backend.dto;

import java.util.List;

// 축제 하나의 상세. 비어 있는 항목은 빈 문자열이고, links 맨 앞이 가장 알맞은 링크다
public record FestivalDetailResponse(
        String contentId,
        String title,
        String addr,
        String image,
        String mapx,
        String mapy,
        String tel,
        String overview,
        String start,
        String end,
        String place,
        String playTime,
        String fee,
        String program,
        String sponsor,
        List<FestivalLink> links
) {
}
