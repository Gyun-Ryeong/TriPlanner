package com.triplanner.backend.common;

import java.util.regex.Pattern;
import org.springframework.http.HttpStatus;
import org.springframework.web.server.ResponseStatusException;

public final class PhoneNumbers {

    private static final Pattern MOBILE_DIGITS = Pattern.compile("^01[016789]\\d{7,8}$");
    private static final Pattern SEPARATORS = Pattern.compile("[\\s-]");

    private PhoneNumbers() {
    }

    // 비어 있으면 null(미등록), 휴대폰 번호면 "010-1234-5678" 형식으로 통일해서 돌려준다
    public static String normalize(String raw) {
        if (raw == null || raw.isBlank()) {
            return null;
        }

        String digits = SEPARATORS.matcher(raw).replaceAll("");
        if (!MOBILE_DIGITS.matcher(digits).matches()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "전화번호 형식이 올바르지 않습니다. (예: 010-1234-5678)");
        }

        int middleEnd = digits.length() == 10 ? 6 : 7;
        return digits.substring(0, 3) + "-" + digits.substring(3, middleEnd) + "-" + digits.substring(middleEnd);
    }
}
