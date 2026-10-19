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

@Entity
@Table(name = "trip_day")
public class TripDay {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "trip_day_id")
    private Long tripDayId;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "trip_id", nullable = false)
    private Trip trip;

    @Column(name = "day_number")
    private Integer dayNumber;

    @Column(name = "date")
    private LocalDate date;

    protected TripDay() {
    }

    public TripDay(Trip trip, Integer dayNumber, LocalDate date) {
        this.trip = trip;
        this.dayNumber = dayNumber;
        this.date = date;
    }

    public Long getTripDayId() {
        return tripDayId;
    }

    public Trip getTrip() {
        return trip;
    }

    public Integer getDayNumber() {
        return dayNumber;
    }

    public LocalDate getDate() {
        return date;
    }
}
