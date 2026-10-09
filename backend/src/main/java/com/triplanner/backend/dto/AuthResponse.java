package com.triplanner.backend.dto;

public record AuthResponse(
        String token,
        Long userId,
        String email,
        String nickname,
        // 프론트에서 관리자 메뉴를 보여줄지 정하는 용도. 실제 권한 검사는 서버가 요청마다 다시 한다
        boolean admin
) {
}
