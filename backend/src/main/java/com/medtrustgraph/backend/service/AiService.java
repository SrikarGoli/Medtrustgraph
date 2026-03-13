package com.medtrustgraph.backend.service;

import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClient;

import com.medtrustgraph.backend.dto.AiResponse;

import java.util.Map;

@Service
@RequiredArgsConstructor
public class AiService {

    private final WebClient.Builder webClientBuilder;

    public AiResponse extractClaims(String text, String patientContext) {
        WebClient webClient = webClientBuilder.baseUrl("http://localhost:8000").build();
        
        // Send BOTH fields to Python!
        Map<String, String> requestBody = Map.of(
            "text", text,
            "patient_context", patientContext != null ? patientContext : ""
        );

        return webClient.post()
            .uri("/extract-claims")
            .bodyValue(requestBody)
            .retrieve()
            .bodyToMono(AiResponse.class)
            .timeout(java.time.Duration.ofSeconds(240)) 
            .block();
    }
    // NEW: Call the baseline endpoint
    public String getBaselineAnswer(String text) {
        WebClient webClient = webClientBuilder.baseUrl("http://localhost:8000").build();
        Map<String, String> requestBody = Map.of("text", text);

        Map response = webClient.post()
            .uri("/baseline-rag")
            .bodyValue(requestBody)
            .retrieve()
            .bodyToMono(Map.class)
            .block();

        return (String) response.get("answer");
    }
}