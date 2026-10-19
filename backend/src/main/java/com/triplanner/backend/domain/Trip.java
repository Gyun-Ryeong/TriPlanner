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
import java.time.LocalDate;
import java.time.LocalDateTime;

@Entity
@Table(name = "trip")
public class Trip {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "trip_id")
    private Long tripId;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "user_id", nullable = false)
    private User user;

    @Column(name = "title")
    private String title;

    @Column(name = "region")
    private String region;

    // 세부 지역(시). 고르지 않았으면 null (권역 전체 기준)
    @Column(name = "city")
    private String city;

    @Column(name = "start_date")
    private LocalDate startDate;

    @Column(name = "end_date")
    private LocalDate endDate;

    @Column(name = "status")
    private String status;

    @Column(name = "created_at")
    private LocalDateTime createdAt;

    // 출발 전 체크리스트 기본 항목을 만들었는지 (사용자가 항목을 모두 지워도 다시 채워지지 않게 한다)
    @Column(name = "checklist_initialized", nullable = false)
    private boolean checklistInitialized = false;

    protected Trip() {
    }

    public Trip(User user, String title, String region, LocalDate startDate, LocalDate endDate, String status) {
        this(user, title, region, null, startDate, endDate, status);
    }

    public Trip(User user, String title, String region, String city, LocalDate startDate, LocalDate endDate, String status) {
        this.user = user;
        this.title = title;
        this.region = region;
        this.city = city;
        this.startDate = startDate;
        this.endDate = endDate;
        this.status = status;
        this.createdAt = LocalDateTime.now();
    }

    public Long getTripId() {
        return tripId;
    }

    public User getUser() {
        return user;
    }

    public String getTitle() {
        return title;
    }

    public String getRegion() {
        return region;
    }

    public String getCity() {
        return city;
    }

    public LocalDate getStartDate() {
        return startDate;
    }

    public LocalDate getEndDate() {
        return endDate;
    }

    public String getStatus() {
        return status;
    }

    public boolean isChecklistInitialized() {
        return checklistInitialized;
    }

    public void markChecklistInitialized() {
        this.checklistInitialized = true;
    }

    public void changeEndDate(LocalDate endDate) {
        this.endDate = endDate;
    }

    public void updateDetails(String title, String region, String city, LocalDate startDate, LocalDate endDate, String status) {
        this.title = title;
        this.region = region;
        this.city = city;
        this.startDate = startDate;
        this.endDate = endDate;
        this.status = status;
    }
}
