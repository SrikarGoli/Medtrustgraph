package com.medtrustgraph.backend.config;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.reactive.function.client.WebClient;

import reactor.netty.http.client.HttpClient;
import org.springframework.http.client.reactive.ReactorClientHttpConnector;

import java.time.Duration;

@Configuration
public class WebClientConfig {

    @Bean
    public WebClient.Builder webClientBuilder() {

        HttpClient httpClient = HttpClient.create()
                .responseTimeout(Duration.ofSeconds(120)); // increase timeout

        return WebClient.builder()
                .clientConnector(new ReactorClientHttpConnector(httpClient));
    }
}