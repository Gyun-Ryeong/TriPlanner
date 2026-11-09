package com.triplanner.backend.dto;

import java.util.Map;

// 한 달치 공휴일. days 는 날짜(yyyy-MM-dd) → 공휴일 이름 (같은 날 겹치면 " · " 로 이어 붙인다).
// available 이 false 면 "공휴일이 없다"가 아니라 "정보를 불러오지 못했다"는 뜻이다 (공공 API 장애·키 미신청)
public record HolidayResponse(int year, int month, Map<String, String> days, boolean available) {

    public static HolidayResponse unavailable(int year, int month) {
        return new HolidayResponse(year, month, Map.of(), false);
    }
}
