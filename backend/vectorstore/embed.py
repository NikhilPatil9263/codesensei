import torch
from transformers import AutoTokenizer, AutoModel
from typing import List
import numpy as np

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

_tokenizer = None
_model = None


def load_model():
    global _tokenizer, _model
    if _tokenizer is None:
        print(f"Loading {MODEL_NAME}...")
        _tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
        _model = AutoModel.from_pretrained(MODEL_NAME)
        _model.eval()
        print("Model loaded.")


def get_embedding(text: str) -> List[float]:
    load_model()
    text = text[:2000]
    inputs = _tokenizer(
        text,
        return_tensors="pt",
        truncation=True,
        max_length=256,
        padding=True
    )
    with torch.no_grad():
        outputs = _model(**inputs)
    embedding = outputs.last_hidden_state.mean(dim=1).squeeze().numpy()
    norm = np.linalg.norm(embedding)
    if norm > 0:
        embedding = embedding / norm
    return embedding.tolist()


def get_embeddings_batch(texts: List[str], batch_size: int = 32) -> List[List[float]]:
    load_model()
    all_embeddings = []
    for i in range(0, len(texts), batch_size):
        batch = [t[:2000] for t in texts[i:i+batch_size]]
        inputs = _tokenizer(
            batch,
            return_tensors="pt",
            truncation=True,
            max_length=256,
            padding=True
        )
        with torch.no_grad():
            outputs = _model(**inputs)
        embeddings = outputs.last_hidden_state.mean(dim=1).numpy()
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        norms = np.where(norms > 0, norms, 1)
        embeddings = embeddings / norms
        all_embeddings.extend(embeddings.tolist())
    return all_embeddings


BUG_QUERIES = [
    "null pointer dereference missing null check",
    "unhandled exception error handling missing try catch",
    "sql injection unsafe query concatenation",
    "race condition concurrent access shared state",
    "memory leak resource not closed",
    "hardcoded password secret api key credential",
    "infinite loop missing break condition",
    "insecure deserialization unsafe input",
    "off-by-one error array bounds checking",
    "type confusion casting unsafe conversion",
]

ARCH_QUERIES = [
    "god class too many responsibilities",
    "circular dependency import cycle",
    "duplicate code copy paste violation",
    "missing abstraction layer tight coupling",
    "deep nesting complexity cognitive load",
    "no error handling bare except pass",
    "global variable mutable shared state",
    "large function too long hard to maintain",
    "mixed concerns business logic presentation",
    "hardcoded constants magic numbers",
]
