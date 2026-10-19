package com.triplanner.backend.dto;

import java.util.List;

// 여행 만들기 화면의 '세부 지역(시)' 선택용: 권역과 그 아래 도시 이름 (외부 API 호출 없이 고정 목록)
public record RegionCatalogResponse(String regionId, String regionName, List<String> cities) {
}
