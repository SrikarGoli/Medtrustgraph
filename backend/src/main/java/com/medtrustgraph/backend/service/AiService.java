package com.medtrustgraph.backend.service;

import com.medtrustgraph.backend.dto.AiResponse;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClient;

import java.time.Duration;
import java.util.Map;

@Service
@RequiredArgsConstructor
public class AiService {

    private final WebClient.Builder webClientBuilder;

    // Helper method to stitch the form fields into a readable paragraph for Gemini
    private String buildPatientContextString(String age, String gender, String diseases, String hereditary, String habits) {
        StringBuilder contextBuilder = new StringBuilder();
        if (age != null && !age.trim().isEmpty()) contextBuilder.append("Age: ").append(age).append(". ");
        if (gender != null && !gender.trim().isEmpty()) contextBuilder.append("Gender: ").append(gender).append(". ");
        if (diseases != null && !diseases.trim().isEmpty()) contextBuilder.append("Chronic Diseases: ").append(diseases).append(". ");
        if (hereditary != null && !hereditary.trim().isEmpty()) contextBuilder.append("Hereditary: ").append(hereditary).append(". ");
        if (habits != null && !habits.trim().isEmpty()) contextBuilder.append("Habits: ").append(habits).append(". ");
        return contextBuilder.toString().trim();
    }

    public AiResponse extractClaims(String text, String age, String gender, String diseases, String hereditary, String habits) {
        String finalPatientContext = buildPatientContextString(age, gender, diseases, hereditary, habits);
        WebClient webClient = webClientBuilder.baseUrl("http://localhost:8000").build();
        
        Map<String, String> requestBody = Map.of(
            "text", text,
            "patient_context", finalPatientContext
        );

        return webClient.post()
            .uri("/extract-claims")
            .bodyValue(requestBody)
            .retrieve()
            .bodyToMono(AiResponse.class)
            .timeout(Duration.ofSeconds(240)) 
            .block();
    }

    public AiResponse analyzeInteractions(String text, String age, String gender, String diseases, String hereditary, String habits) {
        String finalPatientContext = buildPatientContextString(age, gender, diseases, hereditary, habits);
        WebClient webClient = webClientBuilder.baseUrl("http://localhost:8000").build();
        
        Map<String, String> requestBody = Map.of(
            "text", text,
            "patient_context", finalPatientContext
        );

        return webClient.post()
            .uri("/analyze-interactions") // POINTS TO THE NEW PYTHON ENDPOINT
            .bodyValue(requestBody)
            .retrieve()
            .bodyToMono(AiResponse.class)
            .timeout(Duration.ofSeconds(240)) 
            .block();
    }
    
    // UPDATE: Now Baseline RAG also gets the patient context!
    public String getBaselineAnswer(String text, String age, String gender, String diseases, String hereditary, String habits) {
        String finalPatientContext = buildPatientContextString(age, gender, diseases, hereditary, habits);
        WebClient webClient = webClientBuilder.baseUrl("http://localhost:8000").build();
        
        Map<String, String> requestBody = Map.of(
            "text", text,
            "patient_context", finalPatientContext
        );

        try {
            Map response = webClient.post()
                .uri("/baseline-rag")
                .bodyValue(requestBody)
                .retrieve()
                .bodyToMono(Map.class)
                .timeout(Duration.ofSeconds(120))
                .block();
            return response != null ? (String) response.get("answer") : "No baseline available.";
        } catch (Exception e) {
            System.err.println("Baseline RAG Error: " + e.getMessage());
            return "Failed to fetch baseline answer.";
        }
    }
}