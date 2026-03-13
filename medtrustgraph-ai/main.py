import random
import json
# import faiss
from fastapi import FastAPI
from pydantic import BaseModel
from google import genai
from sentence_transformers import SentenceTransformer
import numpy as np
from sklearn.cluster import AgglomerativeClustering
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch
import torch.nn.functional as F
import networkx as nx
import os
import math
import time
import requests
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Optional



app = FastAPI()

# =============================
# CONFIG
# =============================

GEMINI_API_KEY = ""
client = genai.Client(api_key=GEMINI_API_KEY)

embedding_model = SentenceTransformer("all-MiniLM-L6-v2")

# nli_tokenizer = AutoTokenizer.from_pretrained("facebook/bart-large-mnli")
# nli_model = AutoModelForSequenceClassification.from_pretrained("facebook/bart-large-mnli")
nli_tokenizer = AutoTokenizer.from_pretrained("typeform/distilbert-base-uncased-mnli")
nli_model = AutoModelForSequenceClassification.from_pretrained("typeform/distilbert-base-uncased-mnli")

# =====================
# Load corpus
# =====================

# with open("corpus.json", "r") as f:
#     corpus = json.load(f)

# documents = [doc["text"] for doc in corpus]

# # Create embeddings
# doc_embeddings = embedding_model.encode(documents)

# # Build FAISS index
# dimension = doc_embeddings.shape[1]
# index = faiss.IndexFlatL2(dimension)
# index.add(np.array(doc_embeddings))


# =============================
# Request Model
# =============================

class ClaimExtractionRequest(BaseModel):
    text: str
    patient_context: Optional[str] = ""

# =============================
# Health Endpoint
# =============================

@app.get("/health")
def health():
    return {"status": "MedTrustGraph AI (Gemini) running"}



def sigmoid(x):
    return 1 / (1 + math.exp(-x))


# #retrival function

# def retrieve_documents(query, top_k=3):

#     query_embedding = embedding_model.encode([query])
#     distances, indices = index.search(np.array(query_embedding), top_k)

#     retrieved_docs = [documents[i] for i in indices[0]]
#     return retrieved_docs


def get_nli_relation(claim1, claim2, threshold=0.40):
    inputs = nli_tokenizer(claim1, claim2, return_tensors="pt", truncation=True)
    outputs = nli_model(**inputs)

    # Get the raw probabilities
    probs = F.softmax(outputs.logits, dim=1)[0] 
    
    # Based on your label mapping: 0=contradiction, 1=neutral, 2=entailment
    contradiction_prob = probs[0].item()
    entailment_prob = probs[2].item()

    # DEMO HACK: Bypass argmax! Force an edge if the probability is > 40%
    if entailment_prob > threshold:
        return "entailment"
    elif contradiction_prob > threshold:
        return "contradiction"
    
    return "neutral"

# function to propagate trust

def propagate_trust(graph, lambda_factor=0.5, max_iter=20, epsilon=1e-3):
    initial_trust = {n: graph.nodes[n]["trust"] for n in graph.nodes}
    current_trust = initial_trust.copy()
    has_conflict = False

    # 1. Detect High-Conflict Zones before propagation
    for u, v, data in graph.edges(data=True):
        if data["weight"] == -1:
            # If both contradicting nodes come from decent sources (trust > 0.5)
            if initial_trust[u] > 0.5 and initial_trust[v] > 0.5:
                has_conflict = True
                # Optional: You can mark the edge as a "severe conflict" for frontend UI
                graph.edges[u, v]["conflict_zone"] = True

    # 2. Standard Trust Propagation
    for _ in range(max_iter):
        new_trust = {}
        for node in graph.nodes:
            neighbors = list(graph.neighbors(node))
            if len(neighbors) > 0:
                # Heavy penalty for contradiction edges (-1), boost for entailment (1)
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
    """
    Research-Grade Trust Initialization using Evidence Hierarchy, 
    High-Impact Journal Proxy, and Exponential Knowledge Decay.
    """
    # 1. Evidence Hierarchy (Base Trust)
    # Strictly penalizing low-tier and highly rewarding top-tier.
    EVIDENCE_WEIGHTS = {
        "Meta-Analysis": 0.85,
        "Systematic Review": 0.80,
        "Randomized Controlled Trial": 0.75,
        "Clinical Trial": 0.60,
        "Observational Study": 0.45,
        "Case Reports": 0.20
    }

    base_trust = 0.3 # Default baseline for unknown types

    for pt in publication_types:
        for key, weight in EVIDENCE_WEIGHTS.items():
            if key.lower() in pt.lower() and weight > base_trust:
                base_trust = weight

    # 2. High-Impact Journal Bonus (Proxy for Citation/Peer-Review rigor)
    HIGH_IMPACT_JOURNALS = [
        "lancet", 
        "new england journal of medicine", "n engl j med", # Added abbreviation
        "jama", "journal of the american medical association",
        "bmj", "british medical journal", "br med j",      # Added abbreviations
        "nature medicine", "nat med",
        "annals of internal medicine", "ann intern med"
    ]
    
    if journal_title and any(hij in journal_title.lower() for hij in HIGH_IMPACT_JOURNALS):
        base_trust += 0.10

    # 3. Exponential Knowledge Decay (Half-life of medical literature is ~5.5 years)
    # Formula: Trust = Base * e^(-k * age_in_years)
    # k = 0.126 (corresponds to a 5.5 year half-life)
    if year:
        current_year = datetime.now().year
        age = max(0, current_year - year)
        decay_factor = math.exp(-0.126 * age)
        final_trust = base_trust * decay_factor
    else:
        final_trust = base_trust * 0.7 # Penalty for missing date

    return min(max(final_trust, 0.05), 0.95)



import requests
import xml.etree.ElementTree as ET

def retrieve_pubmed_structured(query: str, max_results: int = 15, timeout_sec: int = 10):
    """Fetches full abstracts from PubMed using the efetch XML API."""
    base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    search_params = {
        "db": "pubmed",
        "term": query,
        "retmode": "json",
        "retmax": max_results
    }
    
    try:
        # Phase 1: Search to get PMIDs
        print(f"Fetching PubMed IDs for: {query}...")
        search_resp = requests.get(base_url, params=search_params, timeout=timeout_sec)
        search_resp.raise_for_status()
        id_list = search_resp.json().get("esearchresult", {}).get("idlist", [])
        
        if not id_list:
            return []
            
        # Phase 2: Fetch FULL Abstracts using efetch (XML is the most reliable format for this)
        fetch_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
        fetch_params = {
            "db": "pubmed",
            "id": ",".join(id_list),
            "retmode": "xml"
        }
        
        fetch_resp = requests.get(fetch_url, params=fetch_params, timeout=timeout_sec)
        fetch_resp.raise_for_status()
        
        # Parse the XML response to extract the actual paragraphs of text
        root = ET.fromstring(fetch_resp.content)
        results = []
        
        for article in root.findall(".//PubmedArticle"):
            # Get PMID
            pmid_node = article.find(".//PMID")
            pmid = pmid_node.text if pmid_node is not None else ""
            
            # Get Title
            title_node = article.find(".//ArticleTitle")
            title = title_node.text if title_node is not None else ""
            
            # Get Full Abstract Text (Sometimes abstracts are split into multiple sections)
            abstract_texts = article.findall(".//AbstractText")
            abstract = " ".join([node.text for node in abstract_texts if node.text])
            
            # Get Year
            year = None
            pub_date_year = article.find(".//PubDate/Year")
            if pub_date_year is not None:
                year = int(pub_date_year.text)
                
            # Get Journal Name
            journal_node = article.find(".//Title")
            journal = journal_node.text if journal_node is not None else ""
            
            # Get Publication Types (RCT, Meta-Analysis, etc.)
            pub_types = []
            for pt in article.findall(".//PublicationType"):
                if pt.text:
                    pub_types.append(pt.text)
                    
            # Combine Title and Abstract so the AI has maximum context
            full_text = f"TITLE: {title}\nABSTRACT: {abstract if abstract else 'No abstract available.'}"
            
            if pmid:
                results.append({
                    "pmid": pmid, 
                    "abstract": full_text, # We keep this key named 'abstract' so it works with the rest of your code
                    "publication_types": pub_types, 
                    "year": year, 
                    "journal": journal
                })
                
        return results
        
    except requests.exceptions.Timeout:
        print("WARNING: PubMed API timed out after 10 seconds.")
        return []
    except Exception as e:
        print(f"WARNING: PubMed API Error: {e}")
        return []
# =============================
# Claim Extraction Endpoint
# =============================

@app.post("/extract-claims")
def extract_claims(request: ClaimExtractionRequest):

    # =====================
    # 1. Claim Extraction
    # =====================

    # =====================
    # Retrieval Step (RAG)
    # =====================

    # Local FAISS retrieval
    # local_docs = retrieve_documents(request.text)

    pubmed_docs = retrieve_pubmed_structured(request.text)

    if not pubmed_docs:
        return {
            "nodes": [],
            "edges": [],
            "stable_nodes": [],
            "is_stable": False,
            "confidence_score": 0.0,
            "final_answer": "No relevant PubMed evidence found."
        }
    
    # Merge (PubMed first for authority)
    retrieved_docs = [doc["abstract"] for doc in pubmed_docs]

    # Format documents with indices
    formatted_docs = ""
    for i, doc in enumerate(retrieved_docs):
        formatted_docs += f"\n[Document {i}]\n{doc}\n"

    # =====================
    # NEW: Patient Context Injection
    # =====================
    patient_instruction = ""
    if hasattr(request, 'patient_context') and request.patient_context and request.patient_context.strip():
        patient_instruction = f"""
CRITICAL PATIENT CONTEXT: 
The user is asking this query for a specific patient with the following profile: "{request.patient_context}".
You MUST actively extract claims that highlight specific risks, adverse effects, contraindications, or personalized efficacy for a patient with this exact profile. If a treatment is generally safe but dangerous for this specific patient profile, extract that danger as a distinct atomic claim!
"""

    prompt = f"""
You are an expert medical evidence extraction system building a highly granular neuro-symbolic knowledge graph.

User Question:
{request.text}
{patient_instruction}

You are given multiple medical documents.

Task:
Extract ONLY atomic medical claims that are directly relevant to answering the user question.

CRITICAL RULES FOR GRANULARITY & VOLUME:
1. Break complex findings into multiple, single-fact atomic claims. 
   (Bad: "Aspirin reduces heart attacks but increases gastrointestinal bleeding.")
   (Good: Claim 1: "Aspirin reduces the risk of myocardial infarction.", Claim 2: "Aspirin increases the risk of gastrointestinal bleeding.")
2. Extract a high volume of relevant claims. Aim for 2-4 distinct claims per document if the data supports it (totaling 8-15 claims overall for the graph).
3. Preserve study type information if present (e.g., "In a randomized trial, ...").

Relevance means:
- The claim supports, contradicts, or qualifies a possible answer.
- Ignore procedural details (study enrollment, sample size, trial logistics) unless they directly affect interpretation of the medical outcome.

Return STRICT JSON in this exact format:
[
  {{
    "source_index": 0,
    "claims": ["granular claim 1", "granular claim 2", "granular claim 3"]
  }},
  {{
    "source_index": 1,
    "claims": ["granular claim 4", "granular claim 5"]
  }}
]

Do not include any text, markdown formatting (like ```json), or explanations outside the JSON array.

Documents:
{formatted_docs}
"""

    response = client.models.generate_content(
        model="gemini-flash-lite-latest",
        contents=prompt
    )

    raw_text = response.text if hasattr(response, "text") else ""

    # Clean JSON if wrapped in code blocks
    raw_text = raw_text.replace("```json", "").replace("```", "").strip()

    # Parse JSON response
    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError:
        return {
            "nodes": [],
            "edges": [],
            "stable_nodes": [],
            "is_stable": False,
            "final_answer": "Failed to parse claim extraction response."
        }

    # Build claims list with source mapping
    claims = []
    claim_sources = []
    for doc_entry in parsed:
        source_idx = doc_entry.get("source_index", 0)
        doc_claims = doc_entry.get("claims", [])
        for claim in doc_claims:
            claims.append(claim)
            claim_sources.append(source_idx)

    if len(claims) == 0:
        return {
            "nodes": [],
            "edges": [],
            "stable_nodes": [],
            "is_stable": False,
            "final_answer": "No extractable medical claims found."
        }

    # =====================
    # 1.5 NLI-Aware Semantic Clustering (Deduplication)
    # =====================
    embeddings = embedding_model.encode(claims)
    
    if len(claims) > 1:
        # Step 1: Topical Grouping (Distance 0.25 = ~75% similarity)
        clustering_model = AgglomerativeClustering(
            n_clusters=None, 
            metric='cosine', 
            linkage='average', 
            distance_threshold=0.25
        )
        cluster_labels = clustering_model.fit_predict(embeddings)
    else:
        cluster_labels = [0]
        
    unique_claims = []
    
    for cluster_id in set(cluster_labels):
        indices = [i for i, label in enumerate(cluster_labels) if label == cluster_id]
        
        # Step 2: Stance Splitting via NLI
        # We don't just blindly merge; we verify they entail each other.
        sub_clusters = []
        
        for idx in indices:
            claim_text = claims[idx]
            placed = False
            
            for sub_cluster in sub_clusters:
                rep_text = sub_cluster["claims"][0]
                
                # Ask the NLI model: Do these topically similar claims actually agree?
                relation = get_nli_relation(rep_text, claim_text)
                
                if relation == "entailment":
                    sub_cluster["claims"].append(claim_text)
                    sub_cluster["sources"].add(claim_sources[idx])
                    placed = True
                    break
            
            # If it contradicted or was neutral to existing claims in the topic cluster, start a new sub-cluster
            if not placed:
                sub_clusters.append({
                    "claims": [claim_text],
                    "sources": {claim_sources[idx]}
                })
        
        # Calculate trust for these validated sub-clusters
        for sub_cluster in sub_clusters:
            rep_text = sub_cluster["claims"][0] # Use the first claim as the representative text
            max_trust = 0
            
            for src_idx in sub_cluster["sources"]:
                if src_idx < len(pubmed_docs):
                    doc = pubmed_docs[src_idx]
                    trust = initialize_trust(
                        doc.get("publication_types", []), 
                        doc.get("year", None), 
                        doc.get("journal", "")
                    )
                    max_trust = max(max_trust, trust)
            
            # CORROBORATION BONUS
            if len(sub_cluster["sources"]) > 1:
                final_cluster_trust = min(0.95, max_trust + 0.05)
            else:
                final_cluster_trust = max_trust
                
            unique_claims.append({
                "text": rep_text,
                "trust": final_cluster_trust,
                "sources": list(sub_cluster["sources"])
            })

    # =====================
    # 2. Build Signed Graph
    # =====================
    graph = nx.Graph()

    # Initialize nodes with our Stance-Validated Super-Nodes
    for i, cluster in enumerate(unique_claims):
        graph.add_node(
            i,
            text=cluster["text"],
            trust=cluster["trust"],
            sources=cluster["sources"]
        )

    # Build NLI-based signed edges between the Super-Nodes
    for i in range(len(unique_claims)):
        for j in range(i + 1, len(unique_claims)):
            relation = get_nli_relation(unique_claims[i]["text"], unique_claims[j]["text"])

            if relation == "entailment":
                graph.add_edge(i, j, weight=1)
            elif relation == "contradiction":
                graph.add_edge(i, j, weight=-1)

    # =====================
    # 3. Trust Propagation
    # =====================

    graph, has_conflict = propagate_trust(graph)

    # =====================
    # 4. Collect Node Data
    # =====================

    node_trust = [
        {
            "id": n,
            "text": graph.nodes[n]["text"],
            "trust": float(graph.nodes[n]["trust"])
        }
        for n in graph.nodes
    ]

    edges = [
        {
            "source": u,
            "target": v,
            "weight": data["weight"]
        }
        for u, v, data in graph.edges(data=True)
    ]

    # =====================
    # 5. Stability & Pruning
    # =====================

    TRUST_THRESHOLD = 0.2
    CONFIDENCE_THRESHOLD = 0.3
    GAP_THRESHOLD = 0.1

    # Sort nodes by trust descending
    sorted_nodes = sorted(
        graph.nodes,
        key=lambda n: graph.nodes[n]["trust"],
        reverse=True
    )

    top_trust = graph.nodes[sorted_nodes[0]]["trust"]

    if len(sorted_nodes) > 1:
        second_trust = graph.nodes[sorted_nodes[1]]["trust"]
    else:
        second_trust = 0

    stable_nodes = [
        n for n in graph.nodes
        if graph.nodes[n]["trust"] >= TRUST_THRESHOLD
    ]

    HIGH_TRUST_THRESHOLD = 0.4

    high_trust_nodes = [
        n for n in graph.nodes
        if graph.nodes[n]["trust"] >= HIGH_TRUST_THRESHOLD
    ]

    is_stable = len(high_trust_nodes) > 0

    if len(sorted_nodes) > 1:
        confidence_score = top_trust * (top_trust - second_trust)
    else:
        confidence_score = top_trust * 0.5

    # normalize lower bound
    confidence_score = max(confidence_score, 0.0)

    # =====================
    # 6. If Unstable → Refusal
    # =====================

    if not is_stable:
        return {
            "nodes": node_trust,
            "edges": edges,
            "stable_nodes": stable_nodes,
            "is_stable": False,
            "confidence_score": confidence_score,
            "final_answer": "Insufficient stable evidence to generate a reliable medical conclusion."
        }



    # =====================
    # 7. LLM Gated Answer
    # =====================

    trusted_texts = [graph.nodes[n]["text"] for n in high_trust_nodes]
    trusted_context = "\n".join(trusted_texts)

    # =====================
    # 7. LLM Gated Answer with Citation Grounding
    # =====================

    # Build a context string that explicitly maps claims to their PMIDs
    trusted_context_lines = []
    for n in high_trust_nodes:
        claim_text = graph.nodes[n]["text"]
        source_indices = graph.nodes[n]["sources"]
        
        pmids = []
        for idx in source_indices:
            if idx < len(pubmed_docs):
                pmid = pubmed_docs[idx].get("pmid")
                if pmid:
                    pmids.append(pmid)
        
        pmid_str = ", ".join(pmids) if pmids else "Unknown"
        trusted_context_lines.append(f"- [Claim ID: {n}] [PMIDs: {pmid_str}]: {claim_text}")
        
    trusted_context = "\n".join(trusted_context_lines)

    # Dynamic Prompting based on Graph Topology + Strict Citation Rules
    citation_rules = (
        "\nCRITICAL INSTRUCTION: You are writing a medical research summary. "
        "For EVERY single sentence you generate, you MUST cite the source using the provided PMIDs. "
        "Format your citations exactly like this at the end of the sentence: [PMID: 12345678]. "
        "If a sentence uses multiple claims, combine them: [PMID: 12345678, 87654321]."
    )

    # NEW: Patient Context Rule for the Final Conclusion
    patient_context_val = getattr(request, "patient_context", "")
    patient_warning = ""
    if patient_context_val and patient_context_val.strip():
        patient_warning = f"\n\nCRITICAL PATIENT CONTEXT: You MUST explicitly tailor your final conclusion for a patient with this profile: '{patient_context_val}'. Explicitly state if the evidence graph contains contraindications, specific risks, or unique benefits for this patient profile based on the verified claims."

    if has_conflict:
        system_instruction = (
            "WARNING: The medical evidence graph detected a HIGH CONFLICT between trusted sources. "
            "You MUST acknowledge this debate. Do not pick one side. Contrast the conflicting claims "
            "and explain that the medical community is currently divided based on the literature."
        ) + citation_rules + patient_warning
    else:
        system_instruction = (
            "Provide a definitive, medically cautious conclusion based ONLY on the verified claims. "
            "Do not add outside medical knowledge; only use what is provided below."
        ) + citation_rules + patient_warning

    final_prompt = f"""
{system_instruction}

User Question: {request.text}

Verified Claims & Citations:
{trusted_context}
"""

    answer_response = client.models.generate_content(
        model="gemini-flash-lite-latest",
        contents=final_prompt
    )

    return {
        "nodes": node_trust,
        "edges": edges,
        "stable_nodes": stable_nodes,
        "is_stable": True,
        "has_conflict": has_conflict,
        "confidence_score": confidence_score,
        "final_answer": answer_response.text
    }
    
# =============================
# Baseline RAG Endpoint (For Research Comparison)
# =============================

@app.post("/baseline-rag")
def baseline_rag(request: ClaimExtractionRequest):
    """
    Standard RAG approach: Blindly feed top PubMed abstracts to the LLM 
    without any Trust Graph, NLI verification, or evidence weighting.
    """
    # Fetch same PubMed docs
    pubmed_docs = retrieve_pubmed_structured(request.text)
    
    if not pubmed_docs:
        return {"answer": "No relevant PubMed evidence found."}
        
    # Format documents blindly
    formatted_docs = ""
    for doc in pubmed_docs:
        formatted_docs += f"\n[PMID: {doc['pmid']}]\n{doc['abstract']}\n"
        
    # =====================
    # NEW: Patient Context for Baseline
    # =====================
    patient_context_val = getattr(request, "patient_context", "")
    patient_instruction = ""
    if patient_context_val and patient_context_val.strip():
        patient_instruction = f"\nCRITICAL PATIENT CONTEXT: The user is asking for a patient with this profile: '{patient_context_val}'. You must consider this profile when summarizing the abstracts."

    baseline_prompt = f"""
You are a medical AI assistant. Answer the user's question using ONLY the provided PubMed abstracts.
You must cite the PMIDs at the end of your sentences like this: [PMID: 12345678].

User Question: {request.text}
{patient_instruction}

PubMed Abstracts:
{formatted_docs}
"""

    response = client.models.generate_content(
        model="gemini-flash-lite-latest",
        contents=baseline_prompt
    )
    
    return {"answer": response.text}