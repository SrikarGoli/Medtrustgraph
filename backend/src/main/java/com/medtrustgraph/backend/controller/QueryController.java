package com.medtrustgraph.backend.controller;

import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;
import com.medtrustgraph.backend.service.QueryService;
import com.medtrustgraph.backend.dto.QueryRequest;
import com.medtrustgraph.backend.model.Query;

import java.util.List;

@RestController
@RequestMapping("/api/queries")
@RequiredArgsConstructor
public class QueryController {

    private final QueryService queryService;

    // This now returns immediately with a "Processing..." status
    @PostMapping
    public Query createQuery(@RequestBody QueryRequest request) {
        return queryService.startQueryProcess(request);
    }

    @GetMapping
    public List<Query> getAllQueries() {
        return queryService.getAllQueries();
    }

    // NEW: Endpoint for the frontend to poll the status of a specific query
    @GetMapping("/{id}")
    public Query getQuery(@PathVariable Long id) {
        return queryService.getQueryById(id);
    }

    private final com.medtrustgraph.backend.repository.ClaimRepository claimRepository;

    private final com.medtrustgraph.backend.repository.EdgeRepository edgeRepository; // INJECT THIS

    @GetMapping("/{id}/graph")
    public java.util.Map<String, Object> getQueryGraph(@PathVariable Long id) {
        java.util.List<com.medtrustgraph.backend.model.Claim> nodes = claimRepository.findByQueryId(id);
        java.util.List<com.medtrustgraph.backend.model.Edge> edges = edgeRepository.findByQueryId(id);
        
        return java.util.Map.of("nodes", nodes, "edges", edges);
    }
}