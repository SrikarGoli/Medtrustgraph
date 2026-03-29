# agents.py
import os
from google import genai
from prompts import QUERY_TRANSLATOR_PROMPT

# Load API Key from environment variable
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY environment variable not set. Please set it before running the application.")

client = genai.Client(api_key=GEMINI_API_KEY)

def translate_query_for_pubmed(raw_query: str) -> str:
    """
    Converts conversational medical questions into strict PubMed search keywords.
    """
    formatted_prompt = QUERY_TRANSLATOR_PROMPT.format(raw_query=raw_query)
    
    try:
        response = client.models.generate_content(
            model="gemini-flash-lite-latest",
            contents=formatted_prompt
        )
        keywords = response.text.strip().replace("\n", " ")
        print(f"\n[Query Translator] Converted: '{raw_query}' ---> '{keywords}'\n")
        return keywords
    except Exception as e:
        print(f"WARNING: Query translation failed: {e}")
        return raw_query # Fallback
