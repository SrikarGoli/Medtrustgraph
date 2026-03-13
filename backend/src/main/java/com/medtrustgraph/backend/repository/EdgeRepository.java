package com.medtrustgraph.backend.repository;

import org.springframework.data.jpa.repository.JpaRepository;
import com.medtrustgraph.backend.model.Edge;
import java.util.List;

public interface EdgeRepository extends JpaRepository<Edge, Long> {
    List<Edge> findByQueryId(Long queryId);
}