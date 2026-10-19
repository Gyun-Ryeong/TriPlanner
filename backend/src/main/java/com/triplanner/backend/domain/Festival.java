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

@Entity
@Table(name = "festival")
public class Festival {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "festival_id")
    private Long festivalId;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "place_id", nullable = false)
    private Place place;

    @Column(name = "name")
    private String name;

    @Column(name = "description", columnDefinition = "TEXT")
    private String description;

    public Festival() {
    }

    public Festival(Place place, String name, String description) {
        this.place = place;
        this.name = name;
        this.description = description;
    }
}
