"""
retrieval.py — Hybrid retrieval for CodeSensei

Provides:
  - BM25 keyword search
  - RRF fusion with ChromaDB vector results
  - Neighbor context expansion (prev + current + next chunk)
  - Confidence scoring and threshold filtering
"""

import re
from typing import List, Dict, Optional, Tuple
from rank_bm25 import BM25Okapi

# ── Constants ─────────────────────────────────────────────────────────────────
RRF_K = 60
DEFAULT_CONFIDENCE_THRESHOLD = 0.1
NEIGHBOR_WINDOW = 1
MAX_EXPANDED_CHARS = 6000


# ── Tokenizer ─────────────────────────────────────────────────────────────────
def tokenize(text: str) -> List[str]:
    text = re.sub(r'([a-z])([A-Z])', r'\1 \2', text)
    tokens = re.split(r'[^a-zA-Z0-9]+', text.lower())
    return [t for t in tokens if len(t) > 1]


# ── BM25 ──────────────────────────────────────────────────────────────────────
def build_bm25_index(chunks: List[Dict]) -> BM25Okapi:
    corpus = [tokenize(c["code"]) for c in chunks]
    return BM25Okapi(corpus)


def search_bm25(
    bm25_index: BM25Okapi,
    chunks: List[Dict],
    query: str,
    n_results: int = 10
) -> List[Tuple[Dict, float]]:
    tokens = tokenize(query)
    if not tokens:
        return []
    scores = bm25_index.get_scores(tokens)
    scored = [(chunks[i], float(scores[i])) for i in range(len(chunks))]
    scored.sort(key=lambda x: x[1], reverse=True)
    return [(c, s) for c, s in scored[:n_results] if s > 0.0]


# ── RRF ───────────────────────────────────────────────────────────────────────
def reciprocal_rank_fusion(
    vector_results: List[Dict],
    bm25_results: List[Tuple[Dict, float]],
    k: int = RRF_K
) -> List[Dict]:
    rrf_scores: Dict[str, float] = {}
    chunk_by_id: Dict[str, Dict] = {}

    for rank, chunk in enumerate(vector_results):
        cid = chunk["id"]
        rrf_scores[cid] = rrf_scores.get(cid, 0.0) + 1.0 / (k + rank + 1)
        chunk_by_id[cid] = chunk

    for rank, (chunk, _) in enumerate(bm25_results):
        cid = chunk["id"]
        rrf_scores[cid] = rrf_scores.get(cid, 0.0) + 1.0 / (k + rank + 1)
        chunk_by_id[cid] = chunk

    if not rrf_scores:
        return []

    max_s = max(rrf_scores.values())
    min_s = min(rrf_scores.values())
    rng = max_s - min_s if max_s != min_s else 1.0

    fused = []
    for cid, raw in sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True):
        chunk = chunk_by_id[cid].copy()
        chunk["confidence"] = (raw - min_s) / rng
        chunk["rrf_score"] = raw
        fused.append(chunk)

    return fused


# ── Confidence filter ─────────────────────────────────────────────────────────
def filter_by_confidence(
    chunks: List[Dict],
    threshold: float = DEFAULT_CONFIDENCE_THRESHOLD
) -> List[Dict]:
    return [c for c in chunks if c.get("confidence", 0.0) >= threshold]


# ── Chunk index (per-file ordered) ────────────────────────────────────────────
def build_chunk_index(chunks: List[Dict]) -> Dict[str, List[Dict]]:
    index: Dict[str, List[Dict]] = {}
    for chunk in chunks:
        path = chunk.get("metadata", {}).get("path") or chunk.get("path", "unknown")
        index.setdefault(path, []).append(chunk)
    for path in index:
        index[path].sort(key=lambda c: c.get("metadata", {}).get("start_line", 0))
    return index


# ── Neighbor retrieval ────────────────────────────────────────────────────────
def get_neighbors(
    chunk: Dict,
    file_index: Dict[str, List[Dict]],
    window: int = NEIGHBOR_WINDOW
) -> List[Dict]:
    path = chunk.get("metadata", {}).get("path") or chunk.get("path", "unknown")
    file_chunks = file_index.get(path, [])
    if not file_chunks:
        return [chunk]

    current_idx = None
    for i, fc in enumerate(file_chunks):
        if fc.get("id") == chunk.get("id"):
            current_idx = i
            break

    if current_idx is None:
        return [chunk]

    start = max(0, current_idx - window)
    end = min(len(file_chunks) - 1, current_idx + window)
    return file_chunks[start:end + 1]


def expand_with_neighbors(
    chunks: List[Dict],
    file_index: Dict[str, List[Dict]],
    window: int = NEIGHBOR_WINDOW
) -> List[Dict]:
    seen_ids = set()
    expanded = []

    for central in chunks:
        cid = central.get("id", "")
        if cid in seen_ids:
            continue

        neighbors = get_neighbors(central, file_index, window)
        for n in neighbors:
            seen_ids.add(n.get("id", ""))

        # Find index of central chunk in neighbors list
        central_pos = 0
        for i, n in enumerate(neighbors):
            if n.get("id") == cid:
                central_pos = i
                break

        parts = []
        context_info = []
        for i, n in enumerate(neighbors):
            meta = n.get("metadata", {})
            path = meta.get("path", "unknown")
            start = meta.get("start_line", "?")
            end = meta.get("end_line", "?")
            code = n.get("code", "")

            if i < central_pos:
                label = f"# [CONTEXT - BEFORE] {path} lines {start}-{end}"
            elif n.get("id") == cid:
                label = f"# [CURRENT] {path} lines {start}-{end}"
            else:
                label = f"# [CONTEXT - AFTER] {path} lines {start}-{end}"

            parts.append(f"{label}\n{code}")
            context_info.append(f"{path}:{start}-{end}")

        expanded_code = "\n\n".join(parts)
        if len(expanded_code) > MAX_EXPANDED_CHARS:
            expanded_code = expanded_code[:MAX_EXPANDED_CHARS] + "\n# [TRUNCATED]"

        expanded.append({
            "id": cid,
            "code": expanded_code,
            "metadata": central.get("metadata", {}),
            "distance": central.get("distance", 1.0),
            "confidence": central.get("confidence", 0.0),
            "rrf_score": central.get("rrf_score", 0.0),
            "expanded": True,
            "context_chunks": len(neighbors),
            "context_files": context_info,
        })

    return expanded


# ── Main entry point ──────────────────────────────────────────────────────────
def hybrid_query(
    collection,
    query_embedding: List[float],
    query_text: str,
    bm25_index,
    all_chunks: List[Dict],
    file_index: Dict[str, List[Dict]],
    n_results: int = 10,
    confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
    neighbor_window: int = NEIGHBOR_WINDOW,
) -> List[Dict]:
    # Step 1 — Vector search
    vector_count = min(n_results * 2, collection.count())
    if vector_count == 0:
        return []

    raw = collection.query(
        query_embeddings=[query_embedding],
        n_results=vector_count,
        include=["documents", "metadatas", "distances"]
    )

    vector_results = [
        {
            "id": raw["ids"][0][i],
            "code": raw["documents"][0][i],
            "metadata": raw["metadatas"][0][i],
            "distance": raw["distances"][0][i],
        }
        for i in range(len(raw["ids"][0]))
    ]

    # Step 2 — BM25 search
    bm25_results = []
    if bm25_index is not None and all_chunks and query_text:
        bm25_results = search_bm25(bm25_index, all_chunks, query_text, n_results=n_results * 2)

    # Step 3 — RRF fusion
    if bm25_results:
        fused = reciprocal_rank_fusion(vector_results, bm25_results)
    else:
        fused = []
        for rank, chunk in enumerate(vector_results):
            chunk = chunk.copy()
            chunk["confidence"] = max(0.0, 1.0 - (chunk["distance"] / 2.0))
            chunk["rrf_score"] = 1.0 / (RRF_K + rank + 1)
            fused.append(chunk)

    # Step 4 — Confidence filter
    filtered = filter_by_confidence(fused, confidence_threshold)[:n_results]
    if not filtered:
        return []

    # Step 5 — Neighbor expansion
    return expand_with_neighbors(filtered, file_index, neighbor_window)