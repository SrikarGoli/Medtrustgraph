# agents.py
from google import genai
from prompts import QUERY_TRANSLATOR_PROMPT

# NOTE: Paste your actual API Key here
GEMINI_API_KEY = "AIzaSyCK5A-7WeTB12rR1jXifSHpu7CFj8C6IGs"
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