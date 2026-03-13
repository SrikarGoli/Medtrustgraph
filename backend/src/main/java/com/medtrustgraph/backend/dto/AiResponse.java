package com.medtrustgraph.backend.dto;

import lombok.Data;
import lombok.NoArgsConstructor;
import lombok.AllArgsConstructor;
import java.util.List;

@Data
public class AiResponse {

    private List<NodeDto> nodes;
    private List<EdgeDto> edges;
    private List<Integer> stable_nodes;
    private Boolean is_stable;
    private Boolean has_conflict; 
    private String final_answer;
    private Double confidence_score;
    
    @Data
    @NoArgsConstructor
    @AllArgsConstructor
    public static class NodeDto {
        private Integer id;
        private String text;
        private Double trust;
        private List<Integer> sources; 
    }

    @Data
    @NoArgsConstructor
    @AllArgsConstructor
    public static class EdgeDto {
        private Integer source;
        private Integer target;
        private Integer weight;
    }
}