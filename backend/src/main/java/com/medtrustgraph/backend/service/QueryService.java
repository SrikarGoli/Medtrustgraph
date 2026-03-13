package com.medtrustgraph.backend.service;

import lombok.RequiredArgsConstructor;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Service;

import com.medtrustgraph.backend.model.Claim;
import com.medtrustgraph.backend.model.Edge;
import com.medtrustgraph.backend.model.Query;
import com.medtrustgraph.backend.repository.ClaimRepository;
import com.medtrustgraph.backend.repository.EdgeRepository;
import com.medtrustgraph.backend.repository.QueryRepository;
import com.medtrustgraph.backend.dto.AiResponse;
import com.medtrustgraph.backend.dto.QueryRequest;

import java.time.LocalDateTime;
import java.util.List;
import java.util.stream.Collectors;

@Service
@RequiredArgsConstructor
public class QueryService {

    private final QueryRepository queryRepository;
    private final ClaimRepository claimRepository;
    private final EdgeRepository edgeRepository;
    private final AiService aiService;

    // 1. Synchronous method: Creates the initial record and returns immediately
    public Query startQueryProcess(QueryRequest request) {
        Query query = Query.builder()
            .questionText(request.getQuestionText())
            .patientContext(request.getPatientContext())
            .createdAt(LocalDateTime.now())
            .finalAnswer("Processing... Gathering medical evidence.") // Initial state
            .build();

        Query savedQuery = queryRepository.save(query);
        
        // Kick off the background job
        processAiDataAsync(savedQuery.getId(), request.getQuestionText(),request.getPatientContext());
        
        return savedQuery; // Returns in milliseconds!
    }

    // 2. Asynchronous method: Runs on a separate background thread
    @Async
    public void processAiDataAsync(Long queryId, String questionText, String patientContext) {
        try {
            // 1. Fetch the Standard Baseline Answer (Fast)
            String baselineAnswer = aiService.getBaselineAnswer(questionText);
            
            // 2. Fetch the MedTrustGraph Answer (Takes 15-20 seconds)
            AiResponse aiResponse = aiService.extractClaims(questionText, patientContext);

            // Fetch the pending query from the database
            Query queryToUpdate = queryRepository.findById(queryId).orElseThrow();

            // Update with BOTH results for comparison!
            queryToUpdate.setBaselineAnswer(baselineAnswer); // NEW: Save the baseline
            
            queryToUpdate.setIsStable(aiResponse.getIs_stable());
            queryToUpdate.setHasConflict(aiResponse.getHas_conflict());
            queryToUpdate.setFinalAnswer(aiResponse.getFinal_answer());
            queryToUpdate.setConfidenceScore(aiResponse.getConfidence_score());

            queryRepository.save(queryToUpdate);

            // 1. Save the claims (Nodes)
            if (aiResponse.getNodes() != null) {
                for (AiResponse.NodeDto node : aiResponse.getNodes()) {
                    String sourcesStr = node.getSources() != null ? node.getSources().stream().map(String::valueOf).collect(Collectors.joining(",")) : "";

                    Claim claim = Claim.builder()
                            .claimText(node.getText())
                            .finalTrust(node.getTrust())
                            .isPruned(!aiResponse.getStable_nodes().contains(node.getId()))
                            .sourceIndices(sourcesStr)
                            .aiNodeId(node.getId()) // SAVE THE ID!
                            .query(queryToUpdate)
                            .build();
                    claimRepository.save(claim);
                }
            }

            // 2. Save the Edges
            if (aiResponse.getEdges() != null) {
                for (AiResponse.EdgeDto edgeDto : aiResponse.getEdges()) {
                    Edge edge = Edge.builder()
                            .sourceNode(edgeDto.getSource())
                            .targetNode(edgeDto.getTarget())
                            .weight(edgeDto.getWeight())
                            .query(queryToUpdate)
                            .build();
                    edgeRepository.save(edge);
                }
            }
            System.out.println("Async AI processing complete for Query ID: " + queryId);

        } catch (Exception e) {
            System.err.println("Error during Async AI processing: " + e.getMessage());
            Query queryToUpdate = queryRepository.findById(queryId).orElseThrow();
            queryToUpdate.setFinalAnswer("Error processing medical evidence.");
            queryRepository.save(queryToUpdate);
        }
    }

    public List<Query> getAllQueries() {
        return queryRepository.findAll();
    }
    
    // NEW: Get a single query by ID (useful for frontend polling)
    public Query getQueryById(Long id) {
        return queryRepository.findById(id).orElseThrow();
    }
}