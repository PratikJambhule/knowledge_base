from __future__ import annotations

from pathlib import Path
from typing import Any


COLLECTION_NAME = "knowledgebridge"


class VectorIndexUnavailable(RuntimeError):
    """ChromaDB is unavailable; callers may use SQLite fallback search."""


def chunk_text(text: str, max_chars: int = 1800, overlap: int = 250) -> list[str]:
    paragraphs = [part.strip() for part in text.splitlines() if part.strip()]
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        if current and len(current) + len(paragraph) + 1 > max_chars:
            chunks.append(current)
            current = current[-overlap:] + "\n" + paragraph
        else:
            current = f"{current}\n{paragraph}".strip()
    if current:
        chunks.append(current)
    return chunks or [text[:max_chars]]


def _collection(chroma_dir: str):
    try:
        import chromadb
    except ImportError as exc:
        raise VectorIndexUnavailable("ChromaDB is not installed or available in this environment.") from exc
    Path(chroma_dir).mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=chroma_dir)
    return client.get_or_create_collection(COLLECTION_NAME)


def index_document(chroma_dir: str, document_id: int, text: str, metadata: dict[str, Any]) -> int:
    chunks = chunk_text(text)
    collection = _collection(chroma_dir)
    base_metadata = {key: str(value) for key, value in metadata.items() if value is not None}
    collection.upsert(
        ids=[f"{document_id}:{index}" for index in range(len(chunks))],
        documents=chunks,
        metadatas=[{**base_metadata, "chunk_index": str(index)} for index in range(len(chunks))],
    )
    return len(chunks)


def search_knowledge(chroma_dir: str, query: str, handover_id: int | None = None, limit: int = 5) -> list[dict[str, Any]]:
    collection = _collection(chroma_dir)
    where = {"handover_id": str(handover_id)} if handover_id is not None else None
    result = collection.query(query_texts=[query], n_results=limit, where=where)
    documents = result.get("documents", [[]])[0]
    metadatas = result.get("metadatas", [[]])[0]
    distances = result.get("distances", [[]])[0] or [None] * len(documents)
    return [
        {"text": text, "metadata": metadata or {}, "distance": distance}
        for text, metadata, distance in zip(documents, metadatas, distances)
    ]
