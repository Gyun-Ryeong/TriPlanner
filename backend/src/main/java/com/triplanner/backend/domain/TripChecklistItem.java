package com.triplanner.backend.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.FetchType;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.Table;
import java.time.LocalDateTime;

@Entity
@Table(name = "trip_checklist_item")
public class TripChecklistItem {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "item_id")
    private Long itemId;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "trip_id", nullable = false)
    private Trip trip;

    @Column(name = "content", nullable = false, length = 100)
    private String content;

    // BOOKING(예약) / CHECK(확인) / PACKING(짐) / DEPARTURE(출발) / CUSTOM(직접 추가)
    @Column(name = "category", nullable = false, length = 20)
    private String category;

    // 출발일 며칠 전까지 끝내야 하는지 (0 = 출발 당일). 날짜 대신 일수로 두어, 여행 날짜를 바꿔도 기한이 따라간다
    @Column(name = "due_offset_days", nullable = false)
    private int dueOffsetDays;

    @Column(name = "checked", nullable = false)
    private boolean checked = false;

    @Column(name = "sort_order", nullable = false)
    private int sortOrder;

    @Column(name = "created_at")
    private LocalDateTime createdAt;

    protected TripChecklistItem() {
    }

    public TripChecklistItem(Trip trip, String content, String category, int dueOffsetDays, int sortOrder) {
        this.trip = trip;
        this.content = content;
        this.category = category;
        this.dueOffsetDays = dueOffsetDays;
        this.sortOrder = sortOrder;
        this.createdAt = LocalDateTime.now();
    }

    public Long getItemId() {
        return itemId;
    }

    public Trip getTrip() {
        return trip;
    }

    public String getContent() {
        return content;
    }

    public String getCategory() {
        return category;
    }

    public int getDueOffsetDays() {
        return dueOffsetDays;
    }

    public boolean isChecked() {
        return checked;
    }

    public int getSortOrder() {
        return sortOrder;
    }

    public void setChecked(boolean checked) {
        this.checked = checked;
    }
}
