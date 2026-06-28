import os
import json
import re
from groq import Groq
from typing import Dict, List

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

QUALITY_PROMPT = """You are a senior software engineer doing a code quality assessment.

Analyze this code chunk for style and complexity issues only.

File: {path} (lines {start}–{end})

```
{code}
```

Respond ONLY with a valid JSON object:
{{
  "style_issues": ["list of PEP8 or style problems, empty if none"],
  "complexity_issues": ["list of complexity problems like long functions or deep nesting, empty if none"],
  "readability_score": 75
}}

readability_score must be an integer 0-100 based on how clean and readable this code is.
Return ONLY the JSON. No other text."""


def run_quality_agent(state: Dict) -> Dict:
    state["status"] = "Agent 04 running: checking code quality..."
    print("[Agent 04] Starting code quality analysis...")

    file_paths = state.get("file_paths", [])
    chunks_sample = get_quality_chunks(state)

    style_issues = []
    complexity_issues = []
    readability_scores = []
    test_files = 0
    total_files = len(file_paths)

    # count test files
    for path in file_paths:
        if "test" in path.lower() or "spec" in path.lower():
            test_files += 1

    # detect docstrings and type hints locally — much more reliable than LLM
    docstring_count = 0
    type_hint_count = 0
    comment_count = 0

    for chunk in chunks_sample:
        code = chunk.get("code", "")
        if has_docstring(code):
            docstring_count += 1
        if has_type_hints(code):
            type_hint_count += 1
        if has_comments(code):
            comment_count += 1

    print(f"[Agent 04] Local detection — Docs: {docstring_count}, Types: {type_hint_count}, Comments: {comment_count}")
    print(f"[Agent 04] Sending {min(len(chunks_sample), 15)} chunks to Groq for style/complexity...")

    for chunk in chunks_sample[:15]:
        result = analyse_chunk_quality(chunk)
        if result:
            style_issues.extend(result.get("style_issues") or [])
            complexity_issues.extend(result.get("complexity_issues") or [])
            score = result.get("readability_score")
            if isinstance(score, (int, float)) and 0 <= score <= 100:
                readability_scores.append(int(score))

    total_chunks = max(len(chunks_sample), 1)

    if not readability_scores:
        readability_scores = [70]

    avg_readability = round(sum(readability_scores) / len(readability_scores))
    doc_ratio = round((docstring_count / total_chunks) * 100, 1)
    type_ratio = round((type_hint_count / total_chunks) * 100, 1)
    test_ratio = round((test_files / max(total_files, 1)) * 100, 1)

    quality_score = calculate_quality_score(
        style_issues, complexity_issues,
        avg_readability, doc_ratio, type_ratio, test_ratio
    )

    quality_summary = {
        "quality_score": quality_score,
        "style_issue_count": len(style_issues),
        "complexity_issue_count": len(complexity_issues),
        "style_issues": style_issues[:10],
        "complexity_issues": complexity_issues[:8],
        "avg_readability": avg_readability,
        "docstring_coverage": doc_ratio,
        "type_hint_coverage": type_ratio,
        "test_file_count": test_files,
        "test_coverage_ratio": test_ratio,
        "has_tests": test_files > 0,
    }

    print(f"[Agent 04] Done — Score: {quality_score}/100 | Docs: {doc_ratio}% | Types: {type_ratio}% | Tests: {test_ratio}% | Readability: {avg_readability}%")
    state["quality"] = quality_summary
    state["status"] = "Agent 04 complete."
    return state


def has_docstring(code: str) -> bool:
    patterns = [
        r'"""[\s\S]+?"""',
        r"'''[\s\S]+?'''",
    ]
    for p in patterns:
        if re.search(p, code):
            return True
    return False


def has_type_hints(code: str) -> bool:
    patterns = [
        r'def\s+\w+\s*\([^)]*:\s*\w+',
        r'\)\s*->\s*\w+',
        r':\s*(int|str|float|bool|list|dict|tuple|set|List|Dict|Tuple|Optional|Union|Any|None)\b',
    ]
    for p in patterns:
        if re.search(p, code):
            return True
    return False


def has_comments(code: str) -> bool:
    return bool(re.search(r'#\s*\S+', code))


def get_quality_chunks(state: Dict) -> List[Dict]:
    try:
        from vectorstore.store import get_chroma_client, query_collection
        from vectorstore.embed import get_embedding

        client_chroma = get_chroma_client()
        collection = client_chroma.get_collection(state["collection_name"])

        queries = [
            "function definition implementation logic",
            "class method property attribute",
            "import module utility helper",
        ]

        seen = set()
        chunks = []
        for q in queries:
            emb = get_embedding(q)
            results = query_collection(collection, emb, n_results=8)
            for r in results:
                if r["id"] not in seen:
                    seen.add(r["id"])
                    chunks.append(r)
        return chunks
    except Exception as e:
        print(f"[Agent 04] Could not fetch chunks: {e}")
        return []


def analyse_chunk_quality(chunk: Dict) -> Dict:
    meta = chunk["metadata"]
    prompt = QUALITY_PROMPT.format(
        path=meta["path"],
        start=meta["start_line"],
        end=meta["end_line"],
        code=chunk["code"][:1000]
    )

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=300
        )
        raw = response.choices[0].message.content.strip()
        raw = raw.replace("```json", "").replace("```", "").strip()
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        if match:
            raw = match.group(0)
        return json.loads(raw)
    except Exception as e:
        print(f"[Agent 04] Skipped chunk: {e}")
        return {}


def calculate_quality_score(
    style_issues, complexity_issues,
    avg_readability, doc_ratio, type_ratio, test_ratio
) -> int:
    score = 100
    score -= min(len(style_issues) * 2, 20)
    score -= min(len(complexity_issues) * 3, 20)
    if avg_readability < 50: score -= 15
    elif avg_readability < 70: score -= 8
    elif avg_readability >= 85: score += 5
    if doc_ratio < 20: score -= 15
    elif doc_ratio < 50: score -= 8
    if type_ratio > 70: score += 5
    elif type_ratio < 20: score -= 5
    if test_ratio == 0: score -= 15
    elif test_ratio < 10: score -= 8
    return max(10, min(100, score))