from utils.github_fetcher import fetch_repo_files, get_repo_metadata
from utils.chunker import chunk_files
from vectorstore.embed import get_embeddings_batch
from vectorstore.store import get_chroma_client, get_or_create_collection, store_chunks
from typing import Dict


def run_ingestion_agent(state: Dict) -> Dict:
    repo_url = state["repo_url"]
    github_token = state.get("github_token", "")

    state["status"] = "Agent 01 running: fetching repo files..."
    print(f"[Agent 01] Fetching: {repo_url}")

    metadata = get_repo_metadata(repo_url, github_token)
    files = fetch_repo_files(repo_url, github_token)

    if not files:
        raise ValueError("No supported code files found in this repository.")

    print(f"[Agent 01] Fetched {len(files)} files. Chunking...")
    state["status"] = f"Agent 01: chunking {len(files)} files..."

    chunks = chunk_files(files)
    print(f"[Agent 01] Created {len(chunks)} chunks. Embedding with CodeBERT...")
    state["status"] = f"Agent 01: embedding {len(chunks)} chunks with CodeBERT..."

    texts = [c["code"] for c in chunks]
    embeddings = get_embeddings_batch(texts, batch_size=16)

    client = get_chroma_client()
    repo_name = metadata["full_name"]
    collection = get_or_create_collection(client, repo_name)
    store_chunks(collection, chunks, embeddings)

    print(f"[Agent 01] Done. {len(chunks)} chunks stored in ChromaDB.")

    state["metadata"] = metadata
    state["file_count"] = len(files)
    state["chunk_count"] = len(chunks)
    state["collection_name"] = collection.name
    state["file_paths"] = [f["path"] for f in files]
    state["status"] = "Agent 01 complete."

    return state
