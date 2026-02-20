import random
import json
# import faiss
from fastapi import FastAPI
from pydantic import BaseModel
from google import genai
from sentence_transformers import SentenceTransformer
import numpy as np
# from sklearn.cluster import AgglomerativeClustering
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



app = FastAPI()

# =============================
# CONFIG
# =============================

GEMINI_API_KEY = "AIzaSyCijnTJ_hS6QHXaRVCsptAyMGyed7UG5NQ"
client = genai.Client(api_key=GEMINI_API_KEY)

# embedding_model = SentenceTransformer("all-MiniLM-L6-v2")

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

# function to propagate trust

def propagate_trust(graph, lambda_factor=0.5, max_iter=20, epsilon=1e-3):

    # Initial trust snapshot
    initial_trust = {n: graph.nodes[n]["trust"] for n in graph.nodes}
    current_trust = initial_trust.copy()

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

            raw_value = (
                lambda_factor * initial_trust[node]
                + (1 - lambda_factor) * neighbor_sum
            )

            # Bound trust between 0 and 1
            new_trust[node] = sigmoid(raw_value)

        # Convergence check
        delta = max(abs(new_trust[n] - current_trust[n]) for n in graph.nodes)

        current_trust = new_trust

        if delta < epsilon:
            break

    # Write back final trust
    for node in graph.nodes:
        graph.nodes[node]["trust"] = current_trust[node]

    return graph

def initialize_trust(publication_types, year):
    from datetime import datetime

    base = 0.5

    # -----------------------------
    # Evidence Tier Weight
    # -----------------------------
    EVIDENCE_WEIGHTS = {
        "Meta-Analysis": 0.4,
        "Systematic Review": 0.35,
        "Randomized Controlled Trial": 0.3,
        "Clinical Trial": 0.2,
        "Case Reports": -0.3
    }

    for pt in publication_types:
        for key in EVIDENCE_WEIGHTS:
            if key.lower() in pt.lower():
                base += EVIDENCE_WEIGHTS[key]

    # -----------------------------
    # Recency Weight
    # -----------------------------
    if year:
        current_year = datetime.now().year
        years_old = current_year - year

        recency_bonus = max(0, 0.2 - 0.02 * years_old)
        base += recency_bonus

    return min(max(base, 0.05), 0.95)

# retriving from pubmed

def retrieve_pubmed_structured(query, max_results=3, email="rahulraya665@gmail.com"):
    """
    Retrieve structured PubMed documents using XML.
    Returns list of dicts with:
        - abstract
        - publication_types
        - year
        - pmid
    """

    try:
        # -----------------------------
        # 1️⃣ Search PubMed
        # -----------------------------
        search_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"

        search_params = {
            "db": "pubmed",
            "term": query,
            "retmax": max_results,
            "retmode": "json",
            "sort": "relevance",
            "email": email
        }

        search_response = requests.get(search_url, params=search_params, timeout=10)
        search_response.raise_for_status()

        id_list = search_response.json()["esearchresult"]["idlist"]

        if not id_list:
            return []

        time.sleep(0.3)

        # -----------------------------
        # 2️⃣ Fetch XML Data
        # -----------------------------
        fetch_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"

        fetch_params = {
            "db": "pubmed",
            "id": ",".join(id_list),
            "retmode": "xml",
            "email": email
        }

        fetch_response = requests.get(fetch_url, params=fetch_params, timeout=10)
        fetch_response.raise_for_status()

        root = ET.fromstring(fetch_response.text)

        documents = []

        for article in root.findall(".//PubmedArticle"):

            pmid = article.findtext(".//PMID")

            abstract_texts = [
                elem.text for elem in article.findall(".//AbstractText")
                if elem.text
            ]

            abstract = " ".join(abstract_texts)[:2000]

            publication_types = [
                pt.text for pt in article.findall(".//PublicationType")
                if pt.text
            ]

            year_text = article.findtext(".//PubDate/Year")

            year = None
            if year_text and year_text.isdigit():
                year = int(year_text)

            if abstract:
                documents.append({
                    "pmid": pmid,
                    "abstract": abstract,
                    "publication_types": publication_types,
                    "year": year
                })

        return documents

    except Exception as e:
        print("PubMed XML retrieval error:", str(e))
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

    # PubMed retrieval
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
    # retrieved_docs = pubmed_docs + local_docs
    retrieved_docs = [doc["abstract"] for doc in pubmed_docs]

    # Format documents with indices
    formatted_docs = ""
    for i, doc in enumerate(retrieved_docs):
        formatted_docs += f"\n[Document {i}]\n{doc}\n"

    prompt = f"""
You are a medical evidence extraction system.

User Question:
{request.text}

You are given multiple medical documents.

Task:
Extract ONLY atomic medical claims that are directly relevant to answering the user question.

Relevance means:
- The claim supports, contradicts, or qualifies a possible answer.
- Ignore procedural details (study enrollment, sample size, trial logistics)
  unless they directly affect interpretation of the medical outcome.

Preserve study type information if present (e.g., meta-analysis, randomized trial, case report).

Return STRICT JSON in this format:
[
  {{
    "source_index": 0,
    "claims": ["claim1", "claim2"]
  }},
  {{
    "source_index": 1,
    "claims": ["claim3"]
  }}
]

Do not include any text outside the JSON.

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
    # 2. Build Signed Graph
    # =====================

    graph = nx.Graph()

    # Initialize trust using structured initializer
    for i, claim in enumerate(claims):
        source_idx = claim_sources[i]
        if source_idx >= len(pubmed_docs):
            continue
        source_doc = pubmed_docs[source_idx]

        graph.add_node(
            i,
            text=claim,
            source_doc=source_doc,
            trust=initialize_trust(
                source_doc["publication_types"],
                source_doc["year"]
            )
        )

    # Build NLI-based signed edges
    for i in range(len(claims)):
        for j in range(i + 1, len(claims)):
            relation = get_nli_relation(claims[i], claims[j])

            if relation == "entailment":
                graph.add_edge(i, j, weight=1)
            elif relation == "contradiction":
                graph.add_edge(i, j, weight=-1)

    # =====================
    # 3. Trust Propagation
    # =====================

    graph = propagate_trust(graph)

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

    HIGH_TRUST_THRESHOLD = 0.6

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

    trusted_texts = [
        graph.nodes[n]["text"]
        for n in high_trust_nodes
    ]

    trusted_context = "\n".join(trusted_texts)

    final_prompt = f"""
Answer the medical question using ONLY the following verified claims.

Claims:
{trusted_context}

Provide a medically cautious conclusion.
Do not add new information.
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
        "confidence_score": confidence_score,
        "final_answer": answer_response.text
    }


def get_nli_relation(claim1, claim2):
    inputs = nli_tokenizer(claim1, claim2, return_tensors="pt", truncation=True)
    outputs = nli_model(**inputs)

    probs = F.softmax(outputs.logits, dim=1)
    labels = ["contradiction", "neutral", "entailment"]

    prediction = torch.argmax(probs).item()
    return labels[prediction]