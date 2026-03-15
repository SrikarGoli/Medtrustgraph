# prompts.py

QUERY_TRANSLATOR_PROMPT = """
You are an expert clinical librarian. Your task is to convert the following natural language patient/doctor query into a highly optimized PubMed search string.

CRITICAL RULES:
1. Translate casual medical terms into their official MeSH (Medical Subject Headings) equivalents (e.g., "heart attack" -> "Myocardial Infarction", "painkiller" -> "Analgesics").
2. Format the output using strict PubMed Boolean syntax with appropriate tags (e.g., [MeSH Terms] or [Title/Abstract]).
3. Keep it broad enough to catch 15 good papers, but specific enough to be highly accurate.
4. DO NOT include any conversational text. ONLY output the final PubMed search string.

User Question: {raw_query}

PubMed Search String:
"""

CLAIM_EXTRACTION_PROMPT = """
You are an expert medical evidence extraction system building a highly granular neuro-symbolic knowledge graph.

User Question:
{user_text}
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

BASELINE_RAG_PROMPT = """
You are a medical AI assistant. Answer the user's question using ONLY the provided PubMed abstracts.
You must cite the PMIDs at the end of your sentences like this: [PMID: 12345678].

User Question: {user_text}
{patient_instruction}

PubMed Abstracts:
{formatted_docs}
"""