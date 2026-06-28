import os
import json
from groq import Groq
from vectorstore.embed import get_embedding, ARCH_QUERIES
from vectorstore.store import get_chroma_client, query_collection
from typing import Dict, List

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

ARCH_PROMPT = """You are a principal software architect reviewing a codebase.

Analyze this code for architectural issues, design pattern violations, and structural problems.

File: {path} (lines {start}–{end})

```
{code}
```

Also consider the overall file structure of the repo:
{file_tree}

Respond ONLY with a valid JSON array. Each item must have:
- "category": one of "design", "coupling", "complexity", "maintainability", "scalability"
- "issue": short title (max 10 words)
- "description": what the architectural problem is (2-3 sentences)
- "impact": why this matters at scale (1-2 sentences)
- "recommendation": concrete fix (1-3 sentences)

If no architectural issues exist, return: []

Return ONLY the JSON array, no other text."""


def run_architecture_agent(state: Dict) -> Dict:
    state["status"] = "Agent 03 running: reviewing architecture..."
    print("[Agent 03] Starting architecture review...")

    client_chroma = get_chroma_client()
    collection = client_chroma.get_collection(state["collection_name"])

    arch_chunks = []
    seen_ids = set()

    for query_text in ARCH_QUERIES:
        query_emb = get_embedding(query_text)
        results = query_collection(collection, query_emb, n_results=4)
        for chunk in results:
            if chunk["id"] not in seen_ids and chunk["distance"] < 0.65:
                arch_chunks.append(chunk)
                seen_ids.add(chunk["id"])

    print(f"[Agent 03] Analysing {len(arch_chunks)} chunks for architecture issues...")
    state["status"] = f"Agent 03: reviewing {len(arch_chunks)} code patterns..."

    file_paths = state.get("file_paths", [])
    file_tree_str = build_file_tree_summary(file_paths)

    all_issues = []
    for chunk in arch_chunks[:20]:
        issues = analyse_chunk_for_arch(chunk, file_tree_str)
        all_issues.extend(issues)

    deduplicated = deduplicate_issues(all_issues)

    print(f"[Agent 03] Found {len(deduplicated)} architecture issues.")
    state["arch_issues"] = deduplicated
    state["status"] = "Agent 03 complete."
    return state


def analyse_chunk_for_arch(chunk: Dict, file_tree: str) -> List[Dict]:
    meta = chunk["metadata"]
    prompt = ARCH_PROMPT.format(
        path=meta["path"],
        start=meta["start_line"],
        end=meta["end_line"],
        code=chunk["code"][:1500],
        file_tree=file_tree[:500]
    )

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=800
        )
        raw = response.choices[0].message.content.strip()
        raw = raw.replace("```json", "").replace("```", "").strip()
        issues = json.loads(raw)

        for issue in issues:
            issue["file"] = meta["path"]

        return issues

    except (json.JSONDecodeError, Exception) as e:
        print(f"[Agent 03] Skipped chunk: {e}")
        return []


def build_file_tree_summary(file_paths: List[str]) -> str:
    dirs = {}
    for path in file_paths:
        parts = path.split("/")
        top = parts[0] if len(parts) > 1 else "root"
        dirs.setdefault(top, 0)
        dirs[top] += 1
    lines = [f"{d}/  ({count} files)" for d, count in sorted(dirs.items())]
    return "\n".join(lines[:30])


def deduplicate_issues(issues: List[Dict]) -> List[Dict]:
    seen_titles = set()
    unique = []
    for issue in issues:
        title = issue.get("issue", "").lower()[:40]
        if title not in seen_titles:
            seen_titles.add(title)
            unique.append(issue)
    return unique