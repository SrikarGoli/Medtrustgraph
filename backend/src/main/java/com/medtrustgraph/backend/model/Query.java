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

    private String baselineAnswer;

    private String trustGraphAnswer;

    private Double confidenceScore;

    private Boolean isStable;

    @Column(length = 5000)
    private String finalAnswer;
}