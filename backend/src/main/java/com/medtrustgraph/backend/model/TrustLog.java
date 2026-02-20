package com.medtrustgraph.backend.model;

import jakarta.persistence.*;
import lombok.*;

@Entity
@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class TrustLog {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    private Integer iteration;

    private Double trustValue;

    @ManyToOne
    @JoinColumn(name = "claim_id")
    private Claim claim;
}