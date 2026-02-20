package com.medtrustgraph.backend.repository;

import org.springframework.data.jpa.repository.JpaRepository;
import com.medtrustgraph.backend.model.Query;

public interface QueryRepository extends JpaRepository<Query, Long> {
}
