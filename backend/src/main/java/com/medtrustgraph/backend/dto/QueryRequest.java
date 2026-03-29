package com.medtrustgraph.backend.dto;

import lombok.*;

@Data
public class QueryRequest {
    private String questionText;
    private String age;
    private String gender;
    private String diseases;
    private String hereditary;
    private String habits;
    private String additionalContext; 
}