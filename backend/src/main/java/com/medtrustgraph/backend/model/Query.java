package com.medtrustgraph.backend.model;

import jakarta.persistence.*;
import lombok.*;
import java.time.LocalDateTime;

@Entity
@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class Query {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(length = 2000, nullable = false)
    private String questionText;

    private LocalDateTime createdAt;

    @Column(length=5000)
    private String patientContext; // NEW: Save it to MySQL

    @Column(length = 5000) // NEW: Increased length to prevent data truncation
    private String baselineAnswer;

    private String trustGraphAnswer;

    private Double confidenceScore;

    private Boolean isStable;
    
    private Boolean hasConflict; 

    @Column(length = 5000)
    private String finalAnswer;

    // ... existing fields (questionText, baselineAnswer, finalAnswer, etc.) ...
    
    @Column(name = "patient_age")
    private String age;

    @Column(name = "patient_gender")
    private String gender;

    @Column(columnDefinition = "TEXT")
    private String diseases;

    @Column(columnDefinition = "TEXT")
    private String hereditary;

    @Column(columnDefinition = "TEXT")
    private String habits;
}