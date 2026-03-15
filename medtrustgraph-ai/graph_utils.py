# graph_utils.py
import math
from datetime import datetime

def sigmoid(x):
    return 1 / (1 + math.exp(-x))

def propagate_trust(graph, lambda_factor=0.5, max_iter=20, epsilon=1e-3):
    initial_trust = {n: graph.nodes[n]["trust"] for n in graph.nodes}
    current_trust = initial_trust.copy()
    has_conflict = False

    for u, v, data in graph.edges(data=True):
        if data["weight"] == -1:
            if initial_trust[u] > 0.5 and initial_trust[v] > 0.5:
                has_conflict = True
                graph.edges[u, v]["conflict_zone"] = True

    for _ in range(max_iter):
        new_trust = {}
        for node in graph.nodes:
            neighbors = list(graph.neighbors(node))
            if len(neighbors) > 0:
                neighbor_sum = sum(
                    graph.edges[node, neighbor]["weight"] * current_trust[neighbor]
                    for neighbor in neighbors
                ) / len(neighbors)
            else:
                neighbor_sum = 0

            raw_value = (lambda_factor * initial_trust[node] + (1 - lambda_factor) * neighbor_sum)
            new_trust[node] = sigmoid(raw_value)

        delta = max(abs(new_trust[n] - current_trust[n]) for n in graph.nodes)
        current_trust = new_trust
        if delta < epsilon:
            break

    for node in graph.nodes:
        graph.nodes[node]["trust"] = current_trust[node]

    return graph, has_conflict

def initialize_trust(publication_types, year, journal_title):
    EVIDENCE_WEIGHTS = {
        "Meta-Analysis": 0.85, "Systematic Review": 0.80, "Randomized Controlled Trial": 0.75,
        "Clinical Trial": 0.60, "Observational Study": 0.45, "Case Reports": 0.20
    }
    base_trust = 0.3 

    for pt in publication_types:
        for key, weight in EVIDENCE_WEIGHTS.items():
            if key.lower() in pt.lower() and weight > base_trust:
                base_trust = weight

    HIGH_IMPACT_JOURNALS = [
        "lancet", "new england journal of medicine", "n engl j med", 
        "jama", "journal of the american medical association",
        "bmj", "british medical journal", "br med j", 
        "nature medicine", "nat med", "annals of internal medicine", "ann intern med"
    ]
    
    if journal_title and any(hij in journal_title.lower() for hij in HIGH_IMPACT_JOURNALS):
        base_trust += 0.10

    if year:
        current_year = datetime.now().year
        age = max(0, current_year - year)
        decay_factor = math.exp(-0.126 * age)
        final_trust = base_trust * decay_factor
    else:
        final_trust = base_trust * 0.7 

    return min(max(final_trust, 0.05), 0.95)