package com.medtrustgraph.backend.model;

import jakarta.persistence.*;
import lombok.*;

@Entity
@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class Claim {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(length = 3000)
    private String claimText;

    private Double initialTrust;

    private Double finalTrust;

    private Boolean isPruned;

    @ManyToOne
    @JoinColumn(name = "query_id")
    private Query query;
}
