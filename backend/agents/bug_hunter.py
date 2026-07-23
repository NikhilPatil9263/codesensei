import os
import json
from groq import Groq
from vectorstore.embed import get_embedding, BUG_QUERIES
from vectorstore.store import get_chroma_client, query_collection
from typing import Dict, List

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

BUG_PROMPT = """You are a senior software engineer doing a security and bug review.

Analyze this code chunk and identify concrete bugs, security issues, or critical problems.

File: {path} (lines {start}–{end})
Language: {language}

```
{code}
```

Respond ONLY with a valid JSON array. Each item must have exactly these fields:
- "severity": one of "critical", "high", "medium"
- "issue": short title of the problem (max 10 words)
- "description": what the bug is and why it matters (2-3 sentences)
- "line": approximate line number within the chunk
- "fix": concrete code fix or recommendation (1-3 sentences)
- "confidence": 0.0–1.0 (how certain you are this is a real bug)

If no real bugs exist, return an empty array: []

Return ONLY the JSON array, no other text."""


def run_bug_hunter_agent(state: Dict) -> Dict:
    state["status"] = "Agent 02 running: hunting for bugs..."
    print("[Agent 02] Starting bug hunt...")

    client_chroma = get_chroma_client()
    collection = client_chroma.get_collection(state["collection_name"])

    suspicious_chunks = []
    seen_ids = set()
    chunk_scores = {}

    for query_text in BUG_QUERIES:
        query_emb = get_embedding(query_text)
        results = query_collection(collection, query_emb, n_results=8)  # Increased from 5
        for chunk in results:
            if chunk["id"] not in seen_ids:
                # Weighted scoring: combines distance + query weight
                combined_score = (1 - chunk["distance"]) * 0.5
                if combined_score > 0.35:  # Stricter threshold
                    suspicious_chunks.append(chunk)
                    chunk_scores[chunk["id"]] = combined_score
                    seen_ids.add(chunk["id"])

    # Sort by combined score — review most likely bugs first
    suspicious_chunks.sort(key=lambda x: chunk_scores.get(x["id"], 0), reverse=True)

    print(f"[Agent 02] Found {len(suspicious_chunks)} suspicious chunks. Sending to Groq...")
    state["status"] = f"Agent 02: analysing {len(suspicious_chunks)} suspicious code chunks..."

    all_bugs = []
    for chunk in suspicious_chunks[:25]:
        bugs = analyse_chunk_for_bugs(chunk)
        all_bugs.extend(bugs)

    # Deduplicate bugs by signature
    all_bugs = deduplicate_bugs(all_bugs)
    all_bugs.sort(key=lambda x: {"critical": 0, "high": 1, "medium": 2}.get(x.get("severity", "medium"), 2))

    print(f"[Agent 02] Found {len(all_bugs)} bugs total.")
    state["bugs"] = all_bugs
    state["status"] = "Agent 02 complete."
    return state


def analyse_chunk_for_bugs(chunk: Dict) -> List[Dict]:
    meta = chunk["metadata"]
    prompt = BUG_PROMPT.format(
        path=meta["path"],
        start=meta["start_line"],
        end=meta["end_line"],
        language=meta["language"],
        code=chunk["code"][:1500]
    )

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=1000
        )
        raw = response.choices[0].message.content.strip()
        raw = raw.replace("```json", "").replace("```", "").strip()
        bugs = json.loads(raw)

        for bug in bugs:
            bug["file"] = meta["path"]
            bug["start_line"] = meta["start_line"]
            bug["end_line"] = meta["end_line"]
            bug["code_snippet"] = chunk["code"][:300]

        return [b for b in bugs if b.get("severity") in ("critical", "high", "medium")]

    except (json.JSONDecodeError, Exception) as e:
        print(f"[Agent 02] Skipped chunk due to error: {e}")
        return []


def deduplicate_bugs(bugs: List[Dict]) -> List[Dict]:
    """Remove duplicate bugs by signature."""
    seen = {}
    for bug in bugs:
        sig = (bug.get("file", ""), bug.get("line", 0), bug.get("issue", "")[:40])
        if sig not in seen or bug.get("confidence", 0) > seen[sig].get("confidence", 0):
            seen[sig] = bug
    return list(seen.values())
