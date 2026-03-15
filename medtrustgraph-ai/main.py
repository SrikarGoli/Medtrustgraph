# main.py
import json
import torch
import torch.nn.functional as F
import networkx as nx
import numpy as np
from fastapi import FastAPI
from pydantic import BaseModel
from typing import Optional
from google import genai
from google.genai import types
from sentence_transformers import SentenceTransformer
from sklearn.cluster import AgglomerativeClustering
from transformers import AutoTokenizer, AutoModelForSequenceClassification

# ==== IMPORT MODULAR ARCHITECTURE ====
from prompts import CLAIM_EXTRACTION_PROMPT, BASELINE_RAG_PROMPT
from pubmed_client import retrieve_pubmed_structured
from graph_utils import initialize_trust, propagate_trust
from agents import translate_query_for_pubmed, client # Re-use Gemini client from agents
import itertools

app = FastAPI()

# =============================
# CONFIG & MODELS
# =============================
embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
nli_tokenizer = AutoTokenizer.from_pretrained("typeform/distilbert-base-uncased-mnli")
nli_model = AutoModelForSequenceClassification.from_pretrained("typeform/distilbert-base-uncased-mnli")

class ClaimExtractionRequest(BaseModel):
    text: str
    patient_context: Optional[str] = ""

@app.get("/health")
def health():
    return {"status": "MedTrustGraph Modular Architecture Running"}

def get_nli_relation(claim1, claim2, threshold=0.40):
    inputs = nli_tokenizer(claim1, claim2, return_tensors="pt", truncation=True)
    outputs = nli_model(**inputs)
    probs = F.softmax(outputs.logits, dim=1)[0] 
    contradiction_prob = probs[0].item()
    entailment_prob = probs[2].item()

    if entailment_prob > threshold: return "entailment"
    elif contradiction_prob > threshold: return "contradiction"
    return "neutral"

# =============================
# Claim Extraction Endpoint
# =============================
@app.post("/extract-claims")
def extract_claims(request: ClaimExtractionRequest):
    
    pubmed_docs = retrieve_pubmed_structured(request.text)

    if not pubmed_docs:
        return {"nodes": [], "edges": [], "stable_nodes": [], "is_stable": False, "confidence_score": 0.0, "final_answer": "No relevant PubMed evidence found."}
    
    retrieved_docs = [doc["abstract"] for doc in pubmed_docs]
    formatted_docs = "\n".join([f"\n[Document {i}]\n{doc}\n" for i, doc in enumerate(retrieved_docs)])

    patient_instruction = ""
    if hasattr(request, 'patient_context') and request.patient_context and request.patient_context.strip():
        patient_instruction = f"""
CRITICAL PATIENT CONTEXT: 
The user is asking this query for a specific patient with the following profile: "{request.patient_context}".
You MUST actively extract claims that highlight specific risks, adverse effects, contraindications, or personalized efficacy for a patient with this exact profile.
"""

    prompt = CLAIM_EXTRACTION_PROMPT.format(
        user_text=request.text, 
        patient_instruction=patient_instruction, 
        formatted_docs=formatted_docs
    )

    response = client.models.generate_content(model="gemini-flash-lite-latest", contents=prompt)
    raw_text = (response.text if hasattr(response, "text") else "").replace("```json", "").replace("```", "").strip()

    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError:
        return {"nodes": [], "edges": [], "stable_nodes": [], "is_stable": False, "final_answer": "Failed to parse JSON."}

    claims, claim_sources = [], []
    for doc_entry in parsed:
        for claim in doc_entry.get("claims", []):
            claims.append(claim)
            claim_sources.append(doc_entry.get("source_index", 0))

    if not claims:
        return {"nodes": [], "edges": [], "stable_nodes": [], "is_stable": False, "final_answer": "No extractable medical claims found."}

    # Semantic Clustering
    embeddings = embedding_model.encode(claims)
    cluster_labels = AgglomerativeClustering(n_clusters=None, metric='cosine', linkage='average', distance_threshold=0.25).fit_predict(embeddings) if len(claims) > 1 else [0]
        
    unique_claims = []
    for cluster_id in set(cluster_labels):
        indices = [i for i, label in enumerate(cluster_labels) if label == cluster_id]
        sub_clusters = []
        for idx in indices:
            placed = False
            for sub_cluster in sub_clusters:
                if get_nli_relation(sub_cluster["claims"][0], claims[idx]) == "entailment":
                    sub_cluster["claims"].append(claims[idx])
                    sub_cluster["sources"].add(claim_sources[idx])
                    placed = True
                    break
            if not placed:
                sub_clusters.append({"claims": [claims[idx]], "sources": {claim_sources[idx]}})
        
        for sub_cluster in sub_clusters:
            max_trust = max([initialize_trust(pubmed_docs[s].get("publication_types", []), pubmed_docs[s].get("year", None), pubmed_docs[s].get("journal", "")) for s in sub_cluster["sources"] if s < len(pubmed_docs)] + [0])
            final_cluster_trust = min(0.95, max_trust + 0.05) if len(sub_cluster["sources"]) > 1 else max_trust
            unique_claims.append({"text": sub_cluster["claims"][0], "trust": final_cluster_trust, "sources": list(sub_cluster["sources"])})

    # Graph Build & Propagation
    graph = nx.Graph()
    for i, cluster in enumerate(unique_claims):
        graph.add_node(i, text=cluster["text"], trust=cluster["trust"], sources=cluster["sources"])

    for i in range(len(unique_claims)):
        for j in range(i + 1, len(unique_claims)):
            relation = get_nli_relation(unique_claims[i]["text"], unique_claims[j]["text"])
            if relation == "entailment": graph.add_edge(i, j, weight=1)
            elif relation == "contradiction": graph.add_edge(i, j, weight=-1)

    graph, has_conflict = propagate_trust(graph)

    node_trust = [{"id": n, "text": graph.nodes[n]["text"], "trust": float(graph.nodes[n]["trust"])} for n in graph.nodes]
    edges = [{"source": u, "target": v, "weight": data["weight"]} for u, v, data in graph.edges(data=True)]

    # Stability & Output
    sorted_nodes = sorted(graph.nodes, key=lambda n: graph.nodes[n]["trust"], reverse=True)
    top_trust = graph.nodes[sorted_nodes[0]]["trust"] if sorted_nodes else 0
    second_trust = graph.nodes[sorted_nodes[1]]["trust"] if len(sorted_nodes) > 1 else 0

    stable_nodes = [n for n in graph.nodes if graph.nodes[n]["trust"] >= 0.2]
    high_trust_nodes = [n for n in graph.nodes if graph.nodes[n]["trust"] >= 0.4]

    confidence_score = max(top_trust * (top_trust - second_trust) if len(sorted_nodes) > 1 else top_trust * 0.5, 0.0)

    if not high_trust_nodes:
        return {"nodes": node_trust, "edges": edges, "stable_nodes": stable_nodes, "is_stable": False, "confidence_score": confidence_score, "final_answer": "Insufficient stable evidence."}

    # Final Generation
    trusted_context_lines = []
    for n in high_trust_nodes:
        pmids = [pubmed_docs[idx].get("pmid") for idx in graph.nodes[n]["sources"] if idx < len(pubmed_docs) and pubmed_docs[idx].get("pmid")]
        trusted_context_lines.append(f"- [Claim ID: {n}] [PMIDs: {', '.join(pmids) if pmids else 'Unknown'}]: {graph.nodes[n]['text']}")
        
    citation_rules = "\nCRITICAL INSTRUCTION: You MUST cite the source using the provided PMIDs. Format: [PMID: 12345678]."
    patient_context_val = getattr(request, "patient_context", "")
    patient_warning = f"\n\nCRITICAL PATIENT CONTEXT: Explicitly tailor conclusion for profile: '{patient_context_val}'." if patient_context_val and patient_context_val.strip() else ""

    # NEW: Force beautiful structuring
    formatting_rules = "\nFORMATTING: You MUST use clear formatting. Break your answer into short paragraphs. Use bullet points for listing evidence or risks. Use **bold text** for emphasis."

    sys_inst = ("WARNING: HIGH CONFLICT detected. Acknowledge the debate." if has_conflict else "Provide a definitive conclusion based ONLY on verified claims.") + citation_rules + patient_warning + formatting_rules
    
    final_prompt = f"{sys_inst}\n\nUser Question: {request.text}\n\nVerified Claims:\n{chr(10).join(trusted_context_lines)}"
    
    answer_response = client.models.generate_content(model="gemini-flash-lite-latest", contents=final_prompt)
    return {
        "nodes": node_trust, "edges": edges, "stable_nodes": stable_nodes, 
        "is_stable": True, "has_conflict": has_conflict, "confidence_score": confidence_score, 
        "final_answer": answer_response.text
    }
    
@app.post("/baseline-rag")
def baseline_rag(request: ClaimExtractionRequest):
    
    # ==========================================
    # ROUTER: Is this a normal question or a Polypharmacy Radar?
    # ==========================================
    if request.text.startswith("RADAR_QUERY:"):
        # It's an interaction check!
        drugs_str = request.text.replace("RADAR_QUERY:", "").strip()
        drugs_list = [d.strip() for d in drugs_str.split(",")]
        
        # Build the exact same combinatorial PubMed query so it's a fair fight
        pairs = list(itertools.combinations(drugs_list, 2))
        pair_queries = [f'("{d1}" AND "{d2}")' for d1, d2 in pairs]
        pubmed_query = "(" + " OR ".join(pair_queries) + ') AND ("Drug Interactions"[MeSH] OR "Food-Drug Interactions"[MeSH] OR "Adverse Effects")'
        
        pubmed_docs = retrieve_pubmed_structured(pubmed_query)
        task_text = f"Evaluate the safety and interactions between these items: {drugs_str}."
    else:
        # It's a normal clinical question!
        pubmed_docs = retrieve_pubmed_structured(request.text)
        task_text = request.text
    # ==========================================

    if not pubmed_docs: 
        return {"answer": "No relevant PubMed evidence found for this query."}
        
    formatted_docs = "\n".join([f"\n[PMID: {doc['pmid']}]\n{doc['abstract']}\n" for doc in pubmed_docs])
    patient_context_val = getattr(request, "patient_context", "")
    patient_instruction = f"\nCRITICAL PATIENT CONTEXT: Consider this profile: '{patient_context_val}'." if patient_context_val and patient_context_val.strip() else ""

    formatting_rules = "\nFORMATTING: You MUST use clear formatting. Break your answer into short paragraphs and use bullet points. Use bold text for severe warnings."

    prompt = BASELINE_RAG_PROMPT.format(user_text=task_text, patient_instruction=patient_instruction, formatted_docs=formatted_docs) + formatting_rules
    response = client.models.generate_content(model="gemini-flash-lite-latest", contents=prompt)
    
    return {"answer": response.text}


@app.post("/analyze-interactions")
def analyze_interactions(request: ClaimExtractionRequest):
    # 1. Parse the drugs
    drugs_str = request.text.replace("RADAR_QUERY:", "").strip()
    drugs_list = [d.strip() for d in drugs_str.split(",")]
    
    # 2. Build the Combinatorial PubMed Query
    pairs = list(itertools.combinations(drugs_list, 2))
    pair_queries = [f'("{d1}" AND "{d2}")' for d1, d2 in pairs]
    pubmed_query = "(" + " OR ".join(pair_queries) + ') AND ("Drug Interactions"[MeSH] OR "Food-Drug Interactions"[MeSH] OR "Adverse Effects")'
    
    print(f"\n[RADAR MODE] Fetching: {pubmed_query}")
    pubmed_docs = retrieve_pubmed_structured(pubmed_query)
    
    if not pubmed_docs:
        return {"nodes": [], "edges": [], "is_stable": True, "has_conflict": False, "final_answer": "No documented interactions found in PubMed for this combination.", "confidence_score": 1.0, "stable_nodes": []}

    # 3. Custom Claim Extraction Prompt (Strictly for DDIs)
    formatted_docs = "\n".join([f"\n[PMID: {doc['pmid']}]\n{doc['abstract']}\n" for doc in pubmed_docs])
    extractor_prompt = f"""
    You are a Pharmacovigilance AI. Analyze these abstracts and extract specific claims about drug-drug or drug-food interactions between: {drugs_str}.
    Rules:
    1. Only extract claims that describe an interaction, adverse effect, or contraindication.
    2. Ignore general efficacy claims.
    3. Format as a JSON list of strings.
    
    Abstracts:
    {formatted_docs}
    """
    
    # Extract claims using Gemini
    ext_response = client.models.generate_content(
        model="gemini-flash-lite-latest", 
        contents=extractor_prompt,
        config=types.GenerateContentConfig(response_mime_type="application/json")
    )
    
    import json
    # ... inside /analyze-interactions ...
    
    raw_text = ext_response.text.strip()
    # Aggressively strip markdown formatting if Gemini adds it
    if raw_text.startswith("```json"):
        raw_text = raw_text[7:]
    if raw_text.endswith("```"):
        raw_text = raw_text[:-3]
    raw_text = raw_text.strip()

    try:
        claims = json.loads(raw_text)
    except Exception as e:
        print(f"Failed to parse JSON from Gemini: {e}")
        print(f"Raw output was: {raw_text}")
        claims = []


    if not claims:
        print("No specific interactions extracted by Gemini.")
        return {
            "nodes": [], 
            "edges": [], 
            "is_stable": True, 
            "has_conflict": False, 
            "final_answer": "No adverse interactions or contraindications were found in the literature for this combination.", 
            "confidence_score": 1.0, 
            "stable_nodes": []
        }
    
    # 4. CUSTOM GRAPH INITIALIZATION (No SentenceTransformer needed!)
    nodes = []
    for i, claim in enumerate(claims):
        # We start interaction claims at a high baseline, trusting the literature initially
        nodes.append({"id": f"claim_{i}", "text": claim, "trust": 0.85, "sources": []})

    # 5. NLI Edge Construction (Find Contradictions)
    edges = []
    for i in range(len(nodes)):
        for j in range(i + 1, len(nodes)):
            premise = nodes[i]["text"]
            hypothesis = nodes[j]["text"]
            
            # Use your PyTorch NLI model
            inputs = nli_tokenizer(premise, hypothesis, return_tensors="pt", truncation=True, padding=True).to(device)
            with torch.no_grad():
                logits = nli_model(**inputs).logits
                probs = torch.softmax(logits, dim=1)[0].tolist()
                
            contradiction_prob = probs[2]
            entailment_prob = probs[0]
            
            # Draw edges based on biological agreement/disagreement
            if contradiction_prob > 0.6:
                edges.append({"source": nodes[i]["id"], "target": nodes[j]["id"], "weight": -1})
            elif entailment_prob > 0.7:
                edges.append({"source": nodes[i]["id"], "target": nodes[j]["id"], "weight": 1})

    # 6. PageRank Trust Propagation
    MAX_ITER = 10
    TOLERANCE = 0.01
    has_conflict = any(e["weight"] == -1 for e in edges)
    
    for _ in range(MAX_ITER):
        new_trust = [n["trust"] for n in nodes]
        for idx, node in enumerate(nodes):
            incoming_support = 0
            incoming_attack = 0
            for edge in edges:
                if edge["target"] == node["id"]:
                    source_node = next(n for n in nodes if n["id"] == edge["source"])
                    if edge["weight"] == 1: incoming_support += source_node["trust"]
                    if edge["weight"] == -1: incoming_attack += source_node["trust"]
            
            # Penalize nodes that are contradicted by other trusted papers
            updated_trust = node["trust"] + (0.1 * incoming_support) - (0.2 * incoming_attack)
            new_trust[idx] = max(0.0, min(1.0, updated_trust))
            
        diff = sum(abs(nodes[i]["trust"] - new_trust[i]) for i in range(len(nodes)))
        for i in range(len(nodes)): nodes[i]["trust"] = new_trust[i]
        if diff < TOLERANCE: break

    stable_nodes = [n["id"] for n in nodes if n["trust"] > 0.5]

    # 7. Final Generation
    patient_context_val = getattr(request, "patient_context", "")
    patient_warning = f"\nCRITICAL PATIENT CONTEXT: Explicitly evaluate these interactions against this patient profile: '{patient_context_val}'." if patient_context_val else ""
    
    trusted_claims = [n["text"] for n in nodes if n["id"] in stable_nodes]
    sys_inst = "You are a Clinical Pharmacist AI. Write a definitive interaction report based ONLY on the verified claims." + patient_warning + "\nFORMATTING: Use clear paragraphs and bullet points."
    
    final_prompt = f"{sys_inst}\n\nDrugs to Check: {drugs_str}\n\nVerified Claims:\n{chr(10).join(trusted_claims)}"
    final_answer = client.models.generate_content(model="gemini-flash-lite-latest", contents=final_prompt).text

    return {
        "nodes": nodes,
        "edges": edges,
        "is_stable": len(stable_nodes) > 0,
        "has_conflict": has_conflict,
        "final_answer": final_answer,
        "confidence_score": sum(n["trust"] for n in nodes if n["id"] in stable_nodes) / max(1, len(stable_nodes)),
        "stable_nodes": stable_nodes
    }