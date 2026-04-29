# agents.py
import os
import requests
import json
from dotenv import load_dotenv
from prompts import QUERY_TRANSLATOR_PROMPT

# ==========================================
# 🎚️ THE MAGIC SWITCH
# ==========================================
USE_OLLAMA = False # Set to True for your Colab setup
OLLAMA_MODEL = "llama3.1" 
OLLAMA_URL = "https://sleep-fewer-advised-forums.trycloudflare.com/api/generate"
# ==========================================

load_dotenv()

if USE_OLLAMA:
    print(f"🚀 SYSTEM RUNNING LOCALLY: Routing AI calls to Ollama ({OLLAMA_MODEL})")
    
    class DummyResponse:
        def __init__(self, text):
            self.text = text

    class OllamaClient:
        class Models:
            def generate_content(self, model, contents, config=None):
                payload = {
                    "model": OLLAMA_MODEL,
                    "prompt": contents,
                    "stream": False
                }
                
                is_json_request = False
                if config and getattr(config, 'response_mime_type', '') == "application/json":
                    payload["format"] = "json"
                    is_json_request = True
                
                try:
                    res = requests.post(OLLAMA_URL, json=payload, timeout=300)
                    res.raise_for_status()
                    raw_text = res.json().get('response', '')

                    # --- THE NUCLEAR CLAIM HUNTER ---
                    if is_json_request:
                        print(f"\n[Ollama Raw JSON Preview]: {raw_text[:300]}...\n") 
                        
                        try:
                            clean_text = raw_text.strip()
                            
                            # Safely strip markdown without breaking the code generator
                            md_prefix = "`" * 3
                            if clean_text.startswith(md_prefix + "json"):
                                clean_text = clean_text[7:]
                            elif clean_text.startswith(md_prefix):
                                clean_text = clean_text[3:]
                            if clean_text.endswith(md_prefix):
                                clean_text = clean_text[:-3]
                            clean_text = clean_text.strip()

                            parsed = json.loads(clean_text)
                            extracted_claims = []

                            # Recursive function to hunt ANY string > 25 chars (even if it's a key!)
                            def hunt_for_claims(obj):
                                if isinstance(obj, str):
                                    if len(obj) > 25: 
                                        extracted_claims.append(obj)
                                elif isinstance(obj, list):
                                    for item in obj: 
                                        hunt_for_claims(item)
                                elif isinstance(obj, dict):
                                    for k, v in obj.items():
                                        hunt_for_claims(k) # Local models sometimes put claims in keys!
                                        hunt_for_claims(v)

                            hunt_for_claims(parsed)

                            if extracted_claims:
                                # Deduplicate while preserving order
                                seen = set()
                                unique_claims = [x for x in extracted_claims if not (x in seen or seen.add(x))]
                                final_data = [{"source_index": 0, "claims": unique_claims}]
                                print(f"[JSON Fixer] Successfully reformatted {len(unique_claims)} claims.")
                                return DummyResponse(json.dumps(final_data))
                            else:
                                return DummyResponse(json.dumps([{"source_index": 0, "claims": []}]))

                        except Exception as e:
                            print(f"[JSON Fixer Error] Force-fixing structure: {e}")
                            return DummyResponse(json.dumps([{"source_index": 0, "claims": []}]))

                    return DummyResponse(raw_text)

                except Exception as e:
                    print(f"❌ Ollama API Error: {e}")
                    return DummyResponse(json.dumps([{"source_index": 0, "claims": []}]) if is_json_request else "Error reaching local model.")

        def __init__(self):
            self.models = self.Models()
            
    client = OllamaClient()

else:
    print("☁️ SYSTEM RUNNING ONLINE: Using Google Gemini API")
    from google import genai
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY environment variable not set.")
    client = genai.Client(api_key=GEMINI_API_KEY)

def translate_query_for_pubmed(raw_query: str) -> str:
    formatted_prompt = QUERY_TRANSLATOR_PROMPT.format(raw_query=raw_query)
    try:
        print(f"\n[Query Translator] Running for raw query: '{raw_query}'")
        response = client.models.generate_content(
            model="gemini-flash-lite-latest", 
            contents=formatted_prompt
        )
        keywords = " ".join(response.text.strip().split())
        print(f"[Query Translator] Output PubMed query: '{keywords}'")
        return keywords
    except Exception as e:
        print(f"WARNING: Query translation failed: {e}")
        return raw_query