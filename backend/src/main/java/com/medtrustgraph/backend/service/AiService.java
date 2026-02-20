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

    public AiResponse extractClaims(String text) {

        WebClient webClient = webClientBuilder
                .baseUrl("http://localhost:8000")
                .build();

        Map<String, String> requestBody = Map.of("text", text);

        return webClient.post()
                .uri("/extract-claims")
                .bodyValue(requestBody)
                .retrieve()
                .bodyToMono(AiResponse.class)
                .block();
    }
}