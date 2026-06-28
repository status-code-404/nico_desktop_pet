"""
Conversation collector — batch process dialogue into dimensions.

Flow:
  1. Accumulate ~18 messages (user + assistant)
  2. LLM classifies each into relevant dimensions
  3. Write to ChromaDB per-dimension + SQLite episodic timeline
"""

from __future__ import annotations

import logging
import json
from collections import deque

from .config import DIMENSION_KEYS
from .profile import profile_store
from .store import vector_store

logger = logging.getLogger(__name__)

# Accumulate messages before batch processing
_pending: deque[dict] = deque()
BATCH_SIZE = 18  # process every ~18 messages (user + assistant combined)


def record(source: str, content: str, metadata: dict | None = None):
    """
    Record a conversation turn or system action.
    Auto-flushes to vector store when batch is full.
    """
    entry = {"source": source, "content": content, "metadata": metadata or {}}
    _pending.append(entry)

    # Write to SQLite episodic timeline immediately
    profile_store.add_episode(source, content, metadata=metadata)

    if len(_pending) >= BATCH_SIZE:
        _flush_batch()


def _classify_text(text: str) -> list[str]:
    """
    Classify text into relevant dimensions.
    Uses fast keyword matching; for deeper classification, call LLM.
    """
    keywords = {
        "identity": ["我叫", "我是", "我在", "我住", "我的名字", "所在地", "时区"],
        "work": ["工作", "上班", "加班", "开会", "项目", "代码", "公司", "同事", "老板"],
        "family": ["家人", "爸妈", "妈妈", "爸爸", "老婆", "老公", "孩子", "亲戚"],
        "health": ["睡", "吃", "喝", "运动", "累", "困", "病", "咖啡", "茶", "锻炼", "体重"],
        "learning": ["学习", "学", "课程", "笔记", "考试", "看书", "读书", "论文"],
        "life": ["天气", "车票", "机票", "火车", "酒店", "出行", "外卖", "买菜", "提醒"],
        "interests": ["游戏", "电影", "音乐", "动漫", "书", "爱好", "玩", "画"],
        "goals": ["目标", "计划", "打算", "想要", "希望", "梦想"],
        "preferences": ["喜欢", "不喜欢", "习惯", "风格", "偏好"],
    }
    matched = []
    for dim, kws in keywords.items():
        if any(kw in text for kw in kws):
            matched.append(dim)
    return matched or ["episodic"]


def _classify_with_llm(texts: list[str]) -> dict[str, list[str]]:
    """
    Use LLM to classify each text into dimensions.
    Falls back to keyword matching if LLM unavailable.
    Returns {dimension: [texts...]}.
    """
    # Simple keyword classification for now (fast, offline)
    # LLM-based classification can be added as enhancement
    result: dict[str, list[str]] = {}
    for text in texts:
        dims = _classify_text(text)
        for dim in dims:
            result.setdefault(dim, []).append(text)
    return result


def _flush_batch():
    """Process accumulated messages: classify → write to vector stores."""
    if not _pending:
        return

    entries = list(_pending)
    _pending.clear()

    texts = [e["content"] for e in entries if e["content"].strip()]
    if not texts:
        return

    classified = _classify_with_llm(texts)

    for dim, dim_texts in classified.items():
        vector_store.add(dim, dim_texts)

    # Episodic: store everything
    episodic_texts = [
        f"[{e['source']}] {e['content']}" for e in entries if e["content"].strip()
    ]
    if episodic_texts:
        vector_store.add("episodic", episodic_texts)

    logger.debug("[memory] flushed %d messages → %d dimensions", len(entries), len(classified))


def flush():
    """Force flush pending messages (call on shutdown)."""
    _flush_batch()


def recall(query: str, top_k: int = 5, dimensions: list[str] | None = None) -> list[dict]:
    """Convenience: query vector stores and return results."""
    if dimensions:
        return vector_store.query_all(query, top_k=top_k, dimensions=dimensions)
    return vector_store.query_all(query, top_k=top_k)
