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
import java.time.LocalTime;
import lombok.AccessLevel;
import lombok.Getter;
import lombok.NoArgsConstructor;

@Entity
@Table(name = "trip_item")
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class TripItem {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "trip_item_id")
    private Long tripItemId;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "trip_day_id", nullable = false)
    private TripDay tripDay;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "place_id")
    private Place place;

    @Column(name = "item_type")
    private String itemType;

    @Column(name = "visit_order")
    private Integer visitOrder;

    @Column(name = "start_time")
    private LocalTime startTime;

    @Column(name = "memo")
    private String memo;

    public TripItem(
            TripDay tripDay,
            Place place,
            String itemType,
            Integer visitOrder,
            LocalTime startTime,
            String memo
    ) {
        this.tripDay = tripDay;
        this.place = place;
        this.itemType = itemType;
        this.visitOrder = visitOrder;
        this.startTime = startTime;
        this.memo = memo;
    }
}
