package com.triplanner.backend.dto;

import java.time.LocalDate;

public record ChecklistItemResponse(
        Long itemId,
        String content,
        String category,
        int dueOffsetDays,
        LocalDate dueDate,
        boolean checked
) {
}
