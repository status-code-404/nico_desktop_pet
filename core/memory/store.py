"""
Vector store — ChromaDB with per-dimension collections and built-in ONNX embedding.

Uses ChromaDB's built-in embedding function (lightweight, no torch dependency).
"""

from __future__ import annotations

import logging
import time
import uuid

import chromadb
from chromadb.config import Settings as ChromaSettings
from chromadb.utils import embedding_functions

from .config import DIMENSIONS, CHROMA_DIR

logger = logging.getLogger(__name__)


class VectorStore:
    """ChromaDB-backed vector store with per-dimension collections."""

    def __init__(self):
        self._client = chromadb.PersistentClient(
            path=CHROMA_DIR,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        # Built-in ONNX embedding (lightweight, no torch)
        self._embed_fn = embedding_functions.DefaultEmbeddingFunction()
        self._init_collections()

    def _init_collections(self):
        for key in DIMENSIONS:
            name = DIMENSIONS[key]["collection"]
            try:
                self._client.get_collection(name)
            except Exception:
                self._client.create_collection(
                    name,
                    embedding_function=self._embed_fn,
                    metadata={"dimension": key, "hnsw:space": "cosine"},
                )

    def _collection(self, dimension: str):
        name = DIMENSIONS[dimension]["collection"]
        return self._client.get_collection(
            name, embedding_function=self._embed_fn,
        )

    # ── Write ──────────────────────────────────────────────────

    def add(self, dimension: str, texts: list[str],
             ids: list[str] | None = None, metadatas: list[dict] | None = None):
        if not texts:
            return
        if ids is None:
            ids = [f"{dimension}_{uuid.uuid4().hex[:8]}" for _ in texts]
        t0 = time.monotonic()
        col = self._collection(dimension)
        col.add(documents=texts, ids=ids, metadatas=metadatas)
        ms = int((time.monotonic() - t0) * 1000)
        logger.debug("[memory] %s +%ddocs %dms", dimension, len(texts), ms)

    # ── Query ─────────────────────────────────────────────────

    def query(self, dimension: str, query: str, top_k: int = 5) -> list[dict]:
        t0 = time.monotonic()
        col = self._collection(dimension)
        results = col.query(query_texts=[query], n_results=top_k)
        elapsed = int((time.monotonic() - t0) * 1000)
        logger.debug("[memory] %s '%s' → %dms", dimension, query[:20], elapsed)

        docs = []
        if results["documents"] and results["documents"][0]:
            for i, doc in enumerate(results["documents"][0]):
                dist = results["distances"][0][i] if results.get("distances") else 0.0
                docs.append({"text": doc, "score": round(1.0 - dist, 4), "dimension": dimension})
        return docs

    def query_all(self, query: str, top_k: int = 3,
                   dimensions: list[str] | None = None) -> list[dict]:
        dims = dimensions or list(DIMENSIONS.keys())
        all_results = []
        for dim in dims:
            all_results.extend(self.query(dim, query, top_k=top_k))
        all_results.sort(key=lambda x: x["score"], reverse=True)
        return all_results[:top_k * 2]

    def delete_dimension(self, dimension: str):
        try:
            self._client.delete_collection(DIMENSIONS[dimension]["collection"])
            self._client.create_collection(
                DIMENSIONS[dimension]["collection"],
                embedding_function=self._embed_fn,
                metadata={"dimension": dimension, "hnsw:space": "cosine"},
            )
        except Exception:
            pass


vector_store = VectorStore()

