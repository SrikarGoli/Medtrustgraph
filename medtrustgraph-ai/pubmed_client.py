# pubmed_client.py
import requests
import xml.etree.ElementTree as ET
import time
import re
import json

from agents import translate_query_for_pubmed

# Local memory cache to prevent duplicate PubMed API calls
PUBMED_MEMORY_CACHE = {}

def looks_like_structured_pubmed_query(query: str) -> bool:
    """Detect whether a query already looks like a hand-built PubMed search string."""
    return bool(
        re.search(r"\[[^\]]+\]", query)
        or re.search(r"\b(AND|OR|NOT)\b", query)
        or (("[" in query or "]" in query) and ('"' in query or "(" in query or ")" in query))
    )

def normalize_query_text(text: str) -> str:
    # 1. Strip question marks and exclamation points
    text = text.replace('?', '').replace('!', '')
    text = text.strip()
    
    # 2. CRITICAL FIX: Strip outer brackets if the LLM hallucinates them
    # e.g., ["Metformin" AND "Diabetes"] -> "Metformin" AND "Diabetes"
    if text.startswith('[') and text.endswith(']'):
        text = text[1:-1]
        
    return " ".join(text.strip().split())

def contains_any_phrase(text: str, phrases: list[str]) -> bool:
    lowered = text.lower()
    return any(phrase.lower() in lowered for phrase in phrases)

def validate_translated_query(raw_query: str, translated_query: str) -> tuple[str | None, str | None]:
    """Reject translations that obviously drift away from the original meaning."""
    
    # Prevent the LLM from wrapping the ENTIRE query in [Title/Abstract]
    translated_query = re.sub(r'\)\[Title/Abstract\]$', ')', translated_query, flags=re.IGNORECASE)
    translated_query = re.sub(r'\)\s+\[Title/Abstract\]$', ')', translated_query, flags=re.IGNORECASE)
    translated_query = re.sub(r'\]\s*\[Title/Abstract\]$', ']', translated_query, flags=re.IGNORECASE)

    normalized = normalize_query_text(translated_query)
    raw_normalized = normalize_query_text(raw_query)

    if not normalized:
        return None, "translator returned an empty query"
    if normalized.lower() == raw_normalized.lower():
        return None, "translator returned the same query"
    if re.search(r"\bNOT\b", normalized, flags=re.IGNORECASE):
        return None, "translator introduced a NOT clause"
    if re.search(r'"[^"]+"\*\s*\[MeSH Terms\]', normalized, flags=re.IGNORECASE):
        return None, 'translator used a wildcard inside a MeSH term, which is not valid PubMed MeSH syntax'
    if re.search(r'"Adults"\s*\[MeSH Terms\]', normalized, flags=re.IGNORECASE):
        return None, 'translator used "Adults"[MeSH Terms] instead of the PubMed MeSH heading "Adult"'

    return normalized, None

def retrieve_with_retry(query: str, step_label: str, retries: int = 2) -> list:
    """Uses Exponential Backoff to prevent PubMed 502/429 firewall blocks."""
    print(f"\n[{step_label}] Query -> {query}")
    
    for attempt in range(retries + 1):
        docs = retrieve_pubmed_structured(query)
        if docs:
            return docs
            
        if attempt < retries:
            wait_time = 2 ** (attempt + 1) # Waits 2s, then 4s to cool down the NCBI firewall
            print(f"[{step_label}] API Error or 0 results. Pausing {wait_time}s and retrying...")
            time.sleep(wait_time)
            
    return []

def build_dynamic_pubmed_query(base_text: str, patient_data: dict) -> str:
    """Dynamically builds a PubMed query from patient data fields."""
    if not patient_data:
        return base_text
        
    clinical_keywords = []
    ignore_keys = ['age', 'gender', 'name', 'id'] 
    
    for key, value in patient_data.items():
        if key.lower() not in ignore_keys and isinstance(value, str) and value.strip():
            items = [item.strip() for item in value.split(',') if item.strip()]
            clinical_keywords.extend(items)
            
    if not clinical_keywords:
        return base_text
        
    context_block = " OR ".join([f'"{kw}"' for kw in clinical_keywords])
    return f'({base_text}) AND ({context_block})'

def fetch_pubmed_evidence(base_query: str, patient_data: dict = None, is_medtrust: bool = True) -> list:
    """
    Crystal Clear Retrieval: 
    - Baseline gets a naive, raw text search.
    - MedTrust gets MeSH translation, Patient Constraints, and Fallback logic.
    """
    patient_data = patient_data or {}
    raw_query = normalize_query_text(base_query)
    
    # PERFECT CACHE KEY GENERATION (Ignores empty fields and case variations)
    clean_patient = {k: v for k, v in patient_data.items() if str(v).strip()}
    patient_str = json.dumps(clean_patient, sort_keys=True)
    cache_key = f"{raw_query.lower()}_{patient_str}_medtrust:{is_medtrust}"
    
    if cache_key in PUBMED_MEMORY_CACHE:
        print(f"\n[CACHE HIT] Loaded abstracts instantly from RAM for: {raw_query}")
        return PUBMED_MEMORY_CACHE[cache_key]

    final_docs = []

    # BASELINE RETRIEVAL (Naive)
    if not is_medtrust:
        final_docs = retrieve_with_retry(raw_query, "BASELINE - Naive Raw Search")
    
    # MEDTRUST RETRIEVAL (Neuro-Symbolic)
    else:
        search_query = raw_query
        if not looks_like_structured_pubmed_query(raw_query):
            translated_candidate = translate_query_for_pubmed(raw_query)
            valid_query, rejection_reason = validate_translated_query(raw_query, translated_candidate)
            if valid_query:
                print(f"[Query Translator] Upgraded query to MeSH: '{valid_query}'")
                search_query = valid_query
            else:
                print(f"[Query Translator] Kept raw query. Reason: {rejection_reason}")

        specific_query = build_dynamic_pubmed_query(search_query, patient_data)
        
        # Primary Fetch
        final_docs = retrieve_with_retry(specific_query, "MEDTRUST - Patient Context Search")
        seen_pmids = {doc.get("pmid") for doc in final_docs if doc.get("pmid")}
        
        # Fallback 1: Drop Patient Constraints
        if len(final_docs) < 5 and specific_query != search_query:
            print("[MEDTRUST] Too few specific results. Expanding to general MeSH search...")
            time.sleep(1.0)
            fallback_docs = retrieve_with_retry(search_query, "MEDTRUST - General Fallback Search")
            for doc in fallback_docs:
                pmid = doc.get("pmid")
                if pmid and pmid not in seen_pmids:
                    final_docs.append(doc)
                    seen_pmids.add(pmid)

        # Fallback 2: The Raw Rescue (If LLM hallucinated bad syntax anyway)
        if len(final_docs) < 5 and search_query != raw_query:
            print(f"[MEDTRUST] MeSH translation failed to find papers. Rescuing with original raw query...")
            time.sleep(1.0)
            
            raw_specific = build_dynamic_pubmed_query(raw_query, patient_data)
            rescue_docs = retrieve_with_retry(raw_specific, "MEDTRUST - Raw Context Rescue")
            for doc in rescue_docs:
                pmid = doc.get("pmid")
                if pmid and pmid not in seen_pmids:
                    final_docs.append(doc)
                    seen_pmids.add(pmid)
            
            if len(final_docs) < 5 and raw_specific != raw_query:
                time.sleep(1.0)
                pure_raw_docs = retrieve_with_retry(raw_query, "MEDTRUST - Pure Raw Rescue")
                for doc in pure_raw_docs:
                    pmid = doc.get("pmid")
                    if pmid and pmid not in seen_pmids:
                        final_docs.append(doc)
                        seen_pmids.add(pmid)

    # FINALIZE & CACHE
    final_docs = final_docs[:20]
    print(f"\n[RETRIEVAL SUMMARY] Mode: {'MedTrust' if is_medtrust else 'Baseline'} | Found: {len(final_docs)} papers.")
    
    if final_docs:
        PUBMED_MEMORY_CACHE[cache_key] = final_docs
        
    return final_docs

def retrieve_pubmed_structured(query: str, max_results: int = 15, timeout_sec: int = 15):
    """Fetches full abstracts from PubMed using the efetch XML API."""
    #YOUR_EMAIL = "rahulraya662005@gmail.com"
    YOUR_EMAIL = "srikargoli1@gmail.com"
    TOOL_NAME = "MedTrustGraph_CDSS"
    base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    
    headers = {
        "User-Agent": f"MedTrustGraph_CDSS/1.0 ({YOUR_EMAIL})"
    }
    
    search_params = {
        "db": "pubmed", "term": query, "retmode": "json", 
        "retmax": max_results, "email": YOUR_EMAIL, "tool": TOOL_NAME
    }
    
    try:
        search_resp = requests.get(base_url, params=search_params, headers=headers, timeout=timeout_sec)
        search_resp.raise_for_status()
        id_list = search_resp.json().get("esearchresult", {}).get("idlist", [])
        
        if not id_list:
            return []
            
        fetch_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
        fetch_params = {
            "db": "pubmed", "id": ",".join(id_list), "retmode": "xml",
            "email": YOUR_EMAIL, "tool": TOOL_NAME
        }
        
        fetch_resp = requests.get(fetch_url, params=fetch_params, headers=headers, timeout=timeout_sec)
        fetch_resp.raise_for_status()
        
        root = ET.fromstring(fetch_resp.content)
        results = []
        
        for article in root.findall(".//PubmedArticle"):
            pmid = article.findtext(".//PMID", default="")
            title = article.findtext(".//ArticleTitle", default="")
            abstract = " ".join([node.text for node in article.findall(".//AbstractText") if node.text])
            
            year_node = article.find(".//PubDate/Year")
            year = int(year_node.text) if year_node is not None else None
            journal = article.findtext(".//Title", default="")
            pub_types = [pt.text for pt in article.findall(".//PublicationType") if pt.text]
                    
            if pmid:
                results.append({
                    "pmid": pmid, 
                    "abstract": f"TITLE: {title}\nABSTRACT: {abstract if abstract else 'No abstract available.'}", 
                    "publication_types": pub_types, 
                    "year": year, 
                    "journal": journal
                })
        return results
    except requests.exceptions.RequestException as e:
        # Print a cleaner error message without dumping the whole traceback
        print(f"WARNING: PubMed API Error: {e}")
        return []