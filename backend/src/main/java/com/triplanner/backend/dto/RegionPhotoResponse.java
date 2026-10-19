package com.triplanner.backend.dto;

// 여행 목록에 보여줄 지역 대표 사진. image 가 null 이면 사진을 찾지 못한 것 (화면은 권역 사진으로 대신한다)
public record RegionPhotoResponse(String image, String title, String credit) {

    public static RegionPhotoResponse empty() {
        return new RegionPhotoResponse(null, null, null);
    }
}
