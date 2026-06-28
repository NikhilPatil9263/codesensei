import os
import chromadb
from typing import List, Dict
from dotenv import load_dotenv

load_dotenv()

PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", "./chroma_db")


def get_chroma_client():
    return chromadb.PersistentClient(path=PERSIST_DIR)


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


def store_chunks(collection, chunks: List[Dict], embeddings: List[List[float]]):
    if not chunks or not embeddings:
        return

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
            ids=ids[i:i+batch_size],
            embeddings=embeddings[i:i+batch_size],
            documents=documents[i:i+batch_size],
            metadatas=metadatas[i:i+batch_size]
        )


def query_collection(collection, query_embedding: List[float], n_results: int = 10) -> List[Dict]:
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=min(n_results, collection.count()),
        include=["documents", "metadatas", "distances"]
    )

    chunks = []
    for i in range(len(results["ids"][0])):
        chunks.append({
            "id": results["ids"][0][i],
            "code": results["documents"][0][i],
            "metadata": results["metadatas"][0][i],
            "distance": results["distances"][0][i]
        })
    return chunks