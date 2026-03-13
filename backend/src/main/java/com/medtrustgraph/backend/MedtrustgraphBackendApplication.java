package com.medtrustgraph.backend;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.scheduling.annotation.EnableAsync;

@SpringBootApplication
@EnableAsync // NEW: Enables background thread processing
public class MedtrustgraphBackendApplication {

	public static void main(String[] args) {
		SpringApplication.run(MedtrustgraphBackendApplication.class, args);
	}

}