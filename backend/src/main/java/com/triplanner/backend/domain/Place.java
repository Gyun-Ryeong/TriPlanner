package com.triplanner.backend.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import java.math.BigDecimal;
import java.time.LocalDateTime;

@Entity
@Table(name = "place")
public class Place {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "place_id")
    private Long placeId;

    @Column(name = "content_id", unique = true)
    private String contentId;

    @Column(name = "name")
    private String name;

    @Column(name = "category")
    private String category;

    @Column(name = "address")
    private String address;

    @Column(name = "latitude", precision = 10, scale = 7)
    private BigDecimal latitude;

    @Column(name = "longitude", precision = 10, scale = 7)
    private BigDecimal longitude;

    @Column(name = "description", columnDefinition = "TEXT")
    private String description;

    @Column(name = "updated_at")
    private LocalDateTime updatedAt;

    public Place() {
    }

    public Place(
            String contentId,
            String name,
            String category,
            String address,
            BigDecimal latitude,
            BigDecimal longitude,
            String description
    ) {
        this.contentId = contentId;
        this.name = name;
        this.category = category;
        this.address = address;
        this.latitude = latitude;
        this.longitude = longitude;
        this.description = description;
        this.updatedAt = LocalDateTime.now();
    }

    public Long getPlaceId() {
        return placeId;
    }

    public String getContentId() {
        return contentId;
    }

    public String getName() {
        return name;
    }

    public BigDecimal getLatitude() {
        return latitude;
    }

    public BigDecimal getLongitude() {
        return longitude;
    }
}
