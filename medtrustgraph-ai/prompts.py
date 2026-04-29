# prompts.py

QUERY_TRANSLATOR_PROMPT = """
You are an expert clinical librarian. Your task is to convert the following natural language patient/doctor query into a highly optimized PubMed search string.

CRITICAL RULES:
1. Translate casual medical terms into their official MeSH (Medical Subject Headings) equivalents (e.g., "heart attack" -> "Myocardial Infarction", "painkiller" -> "Analgesics").
2. Format the output using strict PubMed Boolean syntax with appropriate tags (e.g., [MeSH Terms] or [Title/Abstract]).
3. Keep it broad enough to catch 15 good papers, but specific enough to be highly accurate.
4. Prefer 2-4 core concepts. Do NOT over-constrain the search with unnecessary concepts.
5. Only use a MeSH term when it is a precise semantic match. If a phrase is ambiguous, keep it as a simple [Title/Abstract] phrase instead of forcing the wrong MeSH term.
6. Do NOT add NOT clauses, exclusions, or disease filters unless the user explicitly asks to exclude something.
7. Do NOT map time expressions like "long-term use" to unrelated concepts such as care settings. If needed, keep them as plain [Title/Abstract] phrases.
8. When unsure, prioritize recall over precision so the query still returns relevant papers.
9. Preserve the exact medical meaning of the user question. Never replace a general intervention, population, or outcome with a narrower or different clinical concept unless the user explicitly asked for it.
10. DO NOT include any conversational text. ONLY output the final PubMed search string.

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

EXTRACT_CLAIMS_FINAL_PROMPT = """
You are a senior clinical evidence synthesis assistant.
Your job is to answer the user's exact question using ONLY the verified medical claims provided below.

CORE RULES:
1. Use only the verified claims. Do NOT add outside facts, assumptions, or general medical knowledge.
2. Give a direct answer to the user's exact question in the opening sentence.
3. If the conflict flag indicates disagreement, clearly state that the evidence is uncertain, mixed, or contested.
4. If there is no conflict flag, provide a coherent conclusion that best fits the verified claims.
5. If patient context is provided, tailor the answer to that profile without inventing risks or benefits that are not supported by the claims.
6. Do NOT mention the graph, trust propagation, clustering, or internal scoring.
7. Every paragraph and every bullet point must include at least one citation in this format: [PMID: 12345678].
8. The final section must contain bullet points with explicit PMID citations.

WRITING STYLE:
- Sound clinically careful, clear, and useful.
- Prefer synthesis over claim-by-claim dumping.
- Write short, clean paragraphs.
- Avoid hype, overclaiming, vague filler, or meta-explanations.
- Keep the answer polished and structured.

OUTPUT FORMAT:
- Start with a section titled **Conclusion** containing 1 short paragraph that directly answers the question and includes PMID citations.
- Then write a section titled **Why** containing 1 short paragraph that explains the reasoning and includes PMID citations.
- End with a section titled **Supportive Claims** containing 3-6 bullet points of the strongest verified claims, and every bullet must end with PMID citations.
- If any verified claims weaken, qualify, or argue against the conclusion, add one final section titled **Unsupportive Claims** with only those claims as bullet points, each ending with PMID citations.

Conflict Guidance:
{conflict_instruction}

Patient Context:
{patient_instruction}

User Question:
{user_text}

Verified Claims:
{verified_claims}
"""

BASELINE_RAG_PROMPT = """
You are a medical AI assistant. Answer the user's question using ONLY the provided PubMed abstracts.
Do NOT mention PMIDs, paper IDs, or document IDs in your answer.

IMPORTANT BASELINE BEHAVIOR:
- Summarize what the abstracts suggest in plain language.
- If the evidence is unclear or mixed, you may say it is uncertain.
- Do NOT use any external knowledge or hidden reasoning beyond the provided abstracts.
- Do NOT discuss whether the evidence is indirect or limited.

User Question: {user_text}
{patient_instruction}

PubMed Abstracts:
{formatted_docs}
"""
