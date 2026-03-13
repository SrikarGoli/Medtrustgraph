package com.medtrustgraph.backend.repository;

import org.springframework.data.jpa.repository.JpaRepository;
import com.medtrustgraph.backend.model.Claim;
import java.util.List;

public interface ClaimRepository extends JpaRepository<Claim, Long> {
    List<Claim> findByQueryId(Long queryId); // NEW: Fetch nodes for a specific query
}