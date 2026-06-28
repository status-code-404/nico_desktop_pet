"""
Vector store — rapidfuzz fast matching for personal-scale data.

For personal assistant use (hundreds of records, not millions),
fuzzy string matching is 50-100x faster than embedding-based search
while maintaining good recall for Chinese text.
"""

from __future__ import annotations

import logging
import time
import uuid

from rapidfuzz import fuzz, process

from .config import DIMENSIONS

logger = logging.getLogger(__name__)

# In-memory store: {dimension: [(id, text, metadata), ...]}
_store: dict[str, list[tuple[str, str, dict]]] = {}


def _ensure_dim(dimension: str):
    if dimension not in _store:
        _store[dimension] = []


# ── Write ──────────────────────────────────────────────────

def add(dimension: str, texts: list[str],
        ids: list[str] | None = None, metadatas: list[dict] | None = None):
    if not texts:
        return
    _ensure_dim(dimension)
    if ids is None:
        ids = [f"{dimension}_{uuid.uuid4().hex[:8]}" for _ in texts]
    if metadatas is None:
        metadatas = [{} for _ in texts]
    t0 = time.monotonic()
    for i, text in enumerate(texts):
        _store[dimension].append((ids[i], text, metadatas[i]))
    ms = int((time.monotonic() - t0) * 1000)
    logger.debug("[memory] %s +%ddocs %dms", dimension, len(texts), ms)


# ── Query ─────────────────────────────────────────────────

def _query_dim(dimension: str, query_text: str, top_k: int = 5) -> list[dict]:
    _ensure_dim(dimension)
    items = _store[dimension]
    if not items:
        return []

    t0 = time.monotonic()
    texts = [text for _, text, _ in items]
    # rapidfuzz token-set-ratio: fast + good for Chinese
    results = process.extract(
        query_text, texts, scorer=fuzz.token_set_ratio,
        limit=min(top_k, len(texts)),
    )
    ms = int((time.monotonic() - t0) * 1000)
    logger.debug("[memory] %s '%s' → %dms (%d docs)", dimension, query_text[:20], ms, len(texts))

    return [
        {"text": r[0], "score": round(r[1] / 100.0, 4), "dimension": dimension}
        for r in results
    ]


def query_all(query_text: str, top_k: int = 3,
               dimensions: list[str] | None = None) -> list[dict]:
    dims = dimensions or list(DIMENSIONS.keys())
    all_results = []
    t0 = time.monotonic()
    for dim in dims:
        all_results.extend(_query_dim(dim, query_text, top_k=top_k))
    all_results.sort(key=lambda x: x["score"], reverse=True)
    ms = int((time.monotonic() - t0) * 1000)
    logger.debug("[memory] all '%s' → %dms", query_text[:20], ms)
    return all_results[:top_k * 2]


def delete_dimension(dimension: str):
    _store.pop(dimension, None)


# query = _query_dim  (use query_all for cross-dimension, _query_dim for single)
