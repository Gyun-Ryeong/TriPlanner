package com.triplanner.backend.dto;

// kind: homepage(공식 홈페이지) | news(관련 뉴스) | search(이름 검색) | homepage_general(시청 등 관할 기관 첫 화면)
public record FestivalLink(String kind, String label, String url, String title) {
}
