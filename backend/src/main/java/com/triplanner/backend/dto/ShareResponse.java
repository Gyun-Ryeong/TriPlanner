package com.triplanner.backend.dto;

// 공유 링크의 비밀 코드. 화면이 /shared/{shareCode} 주소를 만든다
public record ShareResponse(String shareCode) {
}
