package com.medtrustgraph.backend.dto;

import lombok.*;

@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
public class QueryRequest {
    private String questionText;
    private String patientContext;
}