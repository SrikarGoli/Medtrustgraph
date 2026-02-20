package com.medtrustgraph.backend.service;

import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import com.medtrustgraph.backend.model.Claim;
import com.medtrustgraph.backend.model.Query;
import com.medtrustgraph.backend.repository.ClaimRepository;
import com.medtrustgraph.backend.repository.QueryRepository;
import com.medtrustgraph.backend.dto.AiResponse;
import com.medtrustgraph.backend.dto.QueryRequest;

import java.time.LocalDateTime;
import java.util.List;

@Service
@RequiredArgsConstructor
public class QueryService {

    private final QueryRepository queryRepository;
    private final ClaimRepository claimRepository;
    private final AiService aiService;

    public Query createQuery(QueryRequest request) {

        AiResponse aiResponse = aiService.extractClaims(request.getQuestionText());

        Query query = Query.builder()
            .questionText(request.getQuestionText())
            .createdAt(LocalDateTime.now())
            .isStable(aiResponse.getIs_stable())
            .finalAnswer(aiResponse.getFinal_answer())
            .confidenceScore(aiResponse.getConfidence_score())
            .build();

        Query savedQuery = queryRepository.save(query);

        for (AiResponse.NodeDto node : aiResponse.getNodes()) {

            Claim claim = Claim.builder()
                    .claimText(node.getText())
                    .initialTrust(null)
                    .finalTrust(node.getTrust())
                    .isPruned(!aiResponse.getStable_nodes().contains(node.getId()))
                    .query(savedQuery)
                    .build();

            claimRepository.save(claim);
        }

        return savedQuery;
    }

    public List<Query> getAllQueries() {
        return queryRepository.findAll();
    }
}