"""
store.py — ChromaDB vector store with hybrid retrieval

Module-level registries (built at ingestion, consumed at retrieval):
  bm25_registry  — {collection_name: BM25Okapi}
  chunk_registry — {collection_name: List[Dict]}
  file_registry  — {collection_name: Dict[str, List[Dict]]}

query_collection() API is unchanged — all agents work without modification.
"""

import os
import chromadb
from typing import List, Dict, Optional
from dotenv import load_dotenv

load_dotenv()

PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", "./chroma_db")

# ── Module-level registries ───────────────────────────────────────────────────
bm25_registry: Dict = {}
chunk_registry: Dict = {}
file_registry: Dict = {}


# ── ChromaDB client ───────────────────────────────────────────────────────────
def get_chroma_client():
    return chromadb.PersistentClient(path=PERSIST_DIR)


# ── Collection management ─────────────────────────────────────────────────────
def get_or_create_collection(client, repo_name: str):
    safe_name = repo_name.replace("/", "_").replace("-", "_").lower()
    collection_name = f"repo_{safe_name}"
    try:
        client.delete_collection(collection_name)
    except Exception:
        pass
    return client.create_collection(
        name=collection_name,
        metadata={"hnsw:space": "cosine"}
    )


# ── Store chunks ──────────────────────────────────────────────────────────────
def store_chunks(collection, chunks: List[Dict], embeddings: List[List[float]]):
    if not chunks or not embeddings:
        return

    collection_name = collection.name

    # Store in ChromaDB
    ids = [c["id"] for c in chunks]
    documents = [c["code"] for c in chunks]
    metadatas = [
        {
            "path": c["path"],
            "name": c["name"],
            "type": c["type"],
            "start_line": c["start_line"],
            "end_line": c["end_line"],
            "language": c["language"]
        }
        for c in chunks
    ]

    batch_size = 100
    for i in range(0, len(ids), batch_size):
        collection.add(
            ids=ids[i:i + batch_size],
            embeddings=embeddings[i:i + batch_size],
            documents=documents[i:i + batch_size],
            metadatas=metadatas[i:i + batch_size]
        )

    # Build normalized chunk list for registries
    registry_chunks = [
        {
            "id": c["id"],
            "code": c["code"],
            "path": c["path"],
            "metadata": {
                "path": c["path"],
                "name": c["name"],
                "type": c["type"],
                "start_line": c["start_line"],
                "end_line": c["end_line"],
                "language": c["language"]
            }
        }
        for c in chunks
    ]

    chunk_registry[collection_name] = registry_chunks

    # Build BM25 index
    try:
        from vectorstore.retrieval import build_bm25_index
        bm25_registry[collection_name] = build_bm25_index(registry_chunks)
        print(f"[Store] BM25 index built — {len(chunks)} chunks")
    except Exception as e:
        print(f"[Store] BM25 build failed, vector-only fallback active: {e}")
        bm25_registry[collection_name] = None

    # Build per-file chunk index for neighbor retrieval
    try:
        from vectorstore.retrieval import build_chunk_index
        file_registry[collection_name] = build_chunk_index(registry_chunks)
        print(f"[Store] File index built — {len(file_registry[collection_name])} files")
    except Exception as e:
        print(f"[Store] File index build failed, no neighbor context: {e}")
        file_registry[collection_name] = {}


# ── Query — unchanged API, hybrid retrieval inside ───────────────────────────
def query_collection(
    collection,
    query_embedding: List[float],
    n_results: int = 10,
    query_text: Optional[str] = None,
    confidence_threshold: Optional[float] = None,
) -> List[Dict]:
    """
    Hybrid retrieval with unchanged external API.

    Agents call this exactly as before:
        query_collection(collection, query_emb, n_results=5)

    Internally runs:
        ChromaDB vector search + BM25 + RRF + neighbor expansion + confidence filter

    Falls back to legacy vector-only search if retrieval.py raises any exception.
    """
    collection_name = collection.name
    total = collection.count()

    if total == 0:
        return []

    bm25_index = bm25_registry.get(collection_name)
    all_chunks = chunk_registry.get(collection_name, [])
    file_index = file_registry.get(collection_name, {})

    try:
        from vectorstore.retrieval import hybrid_query, DEFAULT_CONFIDENCE_THRESHOLD

        threshold = (
            confidence_threshold
            if confidence_threshold is not None
            else DEFAULT_CONFIDENCE_THRESHOLD
        )

        return hybrid_query(
            collection=collection,
            query_embedding=query_embedding,
            query_text=query_text or "",
            bm25_index=bm25_index,
            all_chunks=all_chunks,
            file_index=file_index,
            n_results=n_results,
            confidence_threshold=threshold,
        )

    except Exception as e:
        print(f"[Store] Hybrid query failed, using legacy fallback: {e}")
        return _legacy_query(collection, query_embedding, n_results, total)


def _legacy_query(
    collection,
    query_embedding: List[float],
    n_results: int,
    total_chunks: int
) -> List[Dict]:
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=min(n_results, total_chunks),
        include=["documents", "metadatas", "distances"]
    )
    return [
        {
            "id": results["ids"][0][i],
            "code": results["documents"][0][i],
            "metadata": results["metadatas"][0][i],
            "distance": results["distances"][0][i]
        }
        for i in range(len(results["ids"][0]))
    ]