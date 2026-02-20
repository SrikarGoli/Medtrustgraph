package com.medtrustgraph.backend.repository;

import org.springframework.data.jpa.repository.JpaRepository;
import com.medtrustgraph.backend.model.Claim;

public interface ClaimRepository extends JpaRepository<Claim, Long> {
}
