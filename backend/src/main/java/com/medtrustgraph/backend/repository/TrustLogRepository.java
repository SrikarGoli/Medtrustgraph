package com.medtrustgraph.backend.repository;

import org.springframework.data.jpa.repository.JpaRepository;
import com.medtrustgraph.backend.model.TrustLog;

public interface TrustLogRepository extends JpaRepository<TrustLog, Long> {
}