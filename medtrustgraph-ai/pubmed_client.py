# pubmed_client.py
import requests
import xml.etree.ElementTree as ET
from prompts import QUERY_TRANSLATOR_PROMPT

import time

# Local memory cache to prevent duplicate PubMed API calls
PUBMED_MEMORY_CACHE = {}

def fetch_combined_pubmed_evidence(base_query: str, patient_data: dict) -> list:
    """
    Fetches papers for the general query AND the specific patient query, 
    then merges them to ensure we never get 0 results while keeping context.
    """
    cache_key = f"{base_query}_{str(patient_data)}"
    
    # CACHE CHECK
    if cache_key in PUBMED_MEMORY_CACHE:
        print(f"\n[CACHE HIT] Loaded papers instantly from RAM for: {base_query}")
        return PUBMED_MEMORY_CACHE[cache_key]

    specific_query = build_dynamic_pubmed_query(base_query, patient_data)
    
    # STEP 1: GENERAL FETCH
    print(f"\n[HYBRID RETRIEVAL] Step 1: Fetching General -> {base_query}")
    general_docs = retrieve_pubmed_structured(base_query) or []
    
    # THE RETRY SHIELD: If PubMed blocks Step 1, pause and try again!
    if not general_docs:
        print("[RATE LIMIT SHIELD] PubMed blocked Step 1. Pausing for 1 second and retrying...")
        time.sleep(1.0)
        general_docs = retrieve_pubmed_structured(base_query) or []
    
    # THROTTLE: Protect against NCBI limits before moving to Step 2
    time.sleep(0.6) 
    
    # STEP 2: SPECIFIC FETCH
    specific_docs = []
    if specific_query != base_query:
        print(f"[HYBRID RETRIEVAL] Step 2: Fetching Specific -> {specific_query}")
        specific_docs = retrieve_pubmed_structured(specific_query) or []
        
    # COMBINE & REMOVE DUPLICATES
    unique_docs = {}
    
    # Process SPECIFIC docs first so they are at the top of the context window!
    for doc in specific_docs + general_docs:
        pmid = doc.get("pmid")
        if pmid and pmid not in unique_docs:
            unique_docs[pmid] = doc
            
    # Limit to top 20 to prevent Gemini token limit crashes
    final_docs = list(unique_docs.values())[:20]
    print(f"[HYBRID RETRIEVAL] Success: Merged {len(final_docs)} unique papers.")
    
    # Save to RAM
    PUBMED_MEMORY_CACHE[cache_key] = final_docs
    
    return final_docs

def build_dynamic_pubmed_query(base_text: str, patient_data: dict) -> str:
    """Dynamically builds a PubMed query from any future patient data fields."""
    if not patient_data:
        return base_text
        
    clinical_keywords = []
    # Ignore fields that shouldn't be literal search terms in PubMed
    ignore_keys = ['age', 'gender', 'name', 'id'] 
    
    for key, value in patient_data.items():
        if key.lower() not in ignore_keys and isinstance(value, str) and value.strip():
            # If a field has multiple items (e.g., "Hypertension, Smoker"), split them
            items = [item.strip() for item in value.split(',') if item.strip()]
            clinical_keywords.extend(items)
            
    if not clinical_keywords:
        return base_text
        
    # Build the block: ("Hypertension" OR "Smoker" OR "Penicillin Allergy")
    context_block = " OR ".join([f'"{kw}"' for kw in clinical_keywords])
    
    # Final query: (Metformin) AND ("Hypertension" OR "Smoker")
    return f'({base_text}) AND ({context_block})'

def retrieve_pubmed_structured(query: str, max_results: int = 15, timeout_sec: int = 10):
    """Fetches full abstracts from PubMed using the efetch XML API."""
    
    # It is highly recommended to use your real email so NCBI doesn't block your IP
    YOUR_EMAIL = "your email"
    TOOL_NAME = "MedTrustGraph_CDSS"

    base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    search_params = {
        "db": "pubmed",
        "term": query,
        "retmode": "json",
        "retmax": max_results,
        "email": YOUR_EMAIL,
        "tool": TOOL_NAME
    }
    
    try:
        print(f"Fetching PubMed IDs for: {query}...")
        search_resp = requests.get(base_url, params=search_params, timeout=timeout_sec)
        search_resp.raise_for_status()
        id_list = search_resp.json().get("esearchresult", {}).get("idlist", [])
        
        if not id_list:
            print("PubMed returned 0 results for this query.")
            return []
            
        fetch_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
        fetch_params = {
            "db": "pubmed",
            "id": ",".join(id_list),
            "retmode": "xml",
            "email": YOUR_EMAIL,
            "tool": TOOL_NAME
        }
        
        print(f"Fetching full XML abstracts for {len(id_list)} papers...")
        fetch_resp = requests.get(fetch_url, params=fetch_params, timeout=timeout_sec)
        fetch_resp.raise_for_status()
        
        root = ET.fromstring(fetch_resp.content)
        results = []
        
        for article in root.findall(".//PubmedArticle"):
            pmid_node = article.find(".//PMID")
            pmid = pmid_node.text if pmid_node is not None else ""
            
            title_node = article.find(".//ArticleTitle")
            title = title_node.text if title_node is not None else ""
            
            abstract_texts = article.findall(".//AbstractText")
            abstract = " ".join([node.text for node in abstract_texts if node.text])
            
            year = None
            pub_date_year = article.find(".//PubDate/Year")
            if pub_date_year is not None:
                year = int(pub_date_year.text)
                
            journal_node = article.find(".//Title")
            journal = journal_node.text if journal_node is not None else ""
            
            pub_types = []
            for pt in article.findall(".//PublicationType"):
                if pt.text:
                    pub_types.append(pt.text)
                    
            full_text = f"TITLE: {title}\nABSTRACT: {abstract if abstract else 'No abstract available.'}"
            
            if pmid:
                results.append({
                    "pmid": pmid, 
                    "abstract": full_text, 
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
