# pubmed_client.py
import requests
import xml.etree.ElementTree as ET

def retrieve_pubmed_structured(query: str, max_results: int = 15, timeout_sec: int = 10):
    """Fetches full abstracts from PubMed using the efetch XML API."""
    
    # It is highly recommended to use your real email so NCBI doesn't block your IP
    YOUR_EMAIL = "rahulraya665@gmail.com" # <-- REPLACE THIS
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