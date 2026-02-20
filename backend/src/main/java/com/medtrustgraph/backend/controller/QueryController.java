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

    @PostMapping
    public Query createQuery(@RequestBody QueryRequest request) {
        return queryService.createQuery(request);
    }

    @GetMapping
    public List<Query> getAllQueries() {
        return queryService.getAllQueries();
    }
}