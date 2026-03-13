package com.medtrustgraph.backend.model;

import jakarta.persistence.*;
import lombok.*;

@Entity
@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class Edge {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    private Integer sourceNode; // Matches aiNodeId
    private Integer targetNode; // Matches aiNodeId
    private Integer weight;     // 1 for agreement, -1 for contradiction

    @ManyToOne
    @JoinColumn(name = "query_id")
    private Query query;
}