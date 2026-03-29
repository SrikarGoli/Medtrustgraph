package com.medtrustgraph.backend.service;

import com.medtrustgraph.backend.dto.AiResponse;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClient;

import java.time.Duration;
import java.util.HashMap;
import java.util.Map;

@Service
@RequiredArgsConstructor
public class AiService {

    private final WebClient.Builder webClientBuilder;

    // ✨ ADDED additionalContext HERE to stitch it into the Gemini paragraph
    private String buildPatientContextString(String age, String gender, String diseases, String hereditary, String habits, String additionalContext) {
        StringBuilder contextBuilder = new StringBuilder();
        if (age != null && !age.trim().isEmpty()) contextBuilder.append("Age: ").append(age).append(". ");
        if (gender != null && !gender.trim().isEmpty()) contextBuilder.append("Gender: ").append(gender).append(". ");
        if (diseases != null && !diseases.trim().isEmpty()) contextBuilder.append("Chronic Diseases: ").append(diseases).append(". ");
        if (hereditary != null && !hereditary.trim().isEmpty()) contextBuilder.append("Hereditary: ").append(hereditary).append(". ");
        if (habits != null && !habits.trim().isEmpty()) contextBuilder.append("Habits: ").append(habits).append(". ");
        if (additionalContext != null && !additionalContext.trim().isEmpty()) contextBuilder.append("Additional Context: ").append(additionalContext).append(". ");
        return contextBuilder.toString().trim();
    }

    // ✨ ADDED additionalContext HERE to pass it to Python
    private Map<String, Object> buildRequestBody(String text, String finalPatientContext, String age, String gender, String diseases, String hereditary, String habits, String additionalContext) {
        Map<String, Object> requestBody = new HashMap<>();
        requestBody.put("text", text);
        requestBody.put("patient_context", finalPatientContext);
        
        // Passing the specific fields directly to Python's Pydantic model (Handling nulls safely)
        requestBody.put("age", age != null ? age : "");
        requestBody.put("gender", gender != null ? gender : "");
        requestBody.put("diseases", diseases != null ? diseases : "");
        requestBody.put("hereditary", hereditary != null ? hereditary : "");
        requestBody.put("habits", habits != null ? habits : "");
        requestBody.put("additional_context", additionalContext != null ? additionalContext : "");
        
        return requestBody;
    }

    public AiResponse extractClaims(String text, String age, String gender, String diseases, String hereditary, String habits, String additionalContext) {
        String finalPatientContext = buildPatientContextString(age, gender, diseases, hereditary, habits, additionalContext);
        WebClient webClient = webClientBuilder.baseUrl("http://localhost:8000").build();
        
        // USING THE NEW HELPER
        Map<String, Object> requestBody = buildRequestBody(text, finalPatientContext, age, gender, diseases, hereditary, habits, additionalContext);

        return webClient.post()
            .uri("/extract-claims")
            .bodyValue(requestBody)
            .retrieve()
            .bodyToMono(AiResponse.class)
            .timeout(Duration.ofSeconds(240)) 
            .block();
    }

    public AiResponse analyzeInteractions(String text, String age, String gender, String diseases, String hereditary, String habits, String additionalContext) {
        String finalPatientContext = buildPatientContextString(age, gender, diseases, hereditary, habits, additionalContext);
        WebClient webClient = webClientBuilder.baseUrl("http://localhost:8000").build();
        
        // USING THE NEW HELPER
        Map<String, Object> requestBody = buildRequestBody(text, finalPatientContext, age, gender, diseases, hereditary, habits, additionalContext);

        return webClient.post()
            .uri("/analyze-interactions") 
            .bodyValue(requestBody)
            .retrieve()
            .bodyToMono(AiResponse.class)
            .timeout(Duration.ofSeconds(240)) 
            .block();
    }
    
    // UPDATE: Now Baseline RAG also gets the patient context!
    public String getBaselineAnswer(String text, String age, String gender, String diseases, String hereditary, String habits, String additionalContext) {
        String finalPatientContext = buildPatientContextString(age, gender, diseases, hereditary, habits, additionalContext);
        WebClient webClient = webClientBuilder.baseUrl("http://localhost:8000").build();
        
        // USING THE NEW HELPER
        Map<String, Object> requestBody = buildRequestBody(text, finalPatientContext, age, gender, diseases, hereditary, habits, additionalContext);

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