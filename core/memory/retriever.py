"""
Memory retriever — route queries to the right dimension(s), merge results.

Supports:
  - Time-anchored queries: "昨天晚上做了什么"
  - Semantic queries: "我平时几点睡"
  - Cross-dimension: "最近状态怎么样"
  - Vague/episodic: "我刚刚问了什么"
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta

from .config import DIMENSION_KEYS
from .profile import profile_store
from .store import vector_store

logger = logging.getLogger(__name__)

# Time expression patterns (Chinese)
_TIME_PATTERNS = [
    (r"昨天晚上", lambda: (_days_ago(1, 18), _days_ago(1, 23))),
    (r"今天早上", lambda: (_today_at(0), _today_at(12))),
    (r"今天下午", lambda: (_today_at(12), _today_at(18))),
    (r"今天晚上", lambda: (_today_at(18), _today_at(23))),
    (r"今天", lambda: (_today_at(0), _today_at(23))),
    (r"昨天", lambda: (_days_ago(1, 0), _days_ago(1, 23))),
    (r"前天", lambda: (_days_ago(2, 0), _days_ago(2, 24))),
    (r"上周", lambda: (_days_ago(7, 0), _today_at(24))),
    (r"刚刚|刚才|刚刚问|刚才说", lambda: (_minutes_ago(10), _now())),
    (r"最近", lambda: (_days_ago(3, 0), _now())),
]


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _today_at(hour: int) -> str:
    return datetime.now().replace(hour=hour, minute=0, second=0).strftime("%Y-%m-%d %H:%M:%S")


def _days_ago(days: int, hour: int) -> str:
    d = datetime.now() - timedelta(days=days)
    return d.replace(hour=hour, minute=0, second=0).strftime("%Y-%m-%d %H:%M:%S")


def _minutes_ago(minutes: int) -> str:
    return (datetime.now() - timedelta(minutes=minutes)).strftime("%Y-%m-%d %H:%M:%S")


def _parse_time(query: str) -> tuple[str, str] | None:
    """Extract time range from natural language. Returns (start, end) or None."""
    for pattern, fn in _TIME_PATTERNS:
        if re.search(pattern, query):
            return fn()
    return None


# Dimension routing keywords
_DIM_ROUTING = {
    "identity": ["我是谁", "我叫什么", "我住哪", "我的名字"],
    "work": ["工作", "上班", "开会", "项目", "代码", "同事"],
    "family": ["家人", "爸妈", "老婆", "老公", "孩子", "亲戚", "回家"],
    "health": ["睡", "吃", "喝", "运动", "累", "困", "病了", "体检", "体重", "锻炼"],
    "learning": ["学", "课程", "考试", "看书", "笔记"],
    "life": ["天气", "车票", "机票", "酒店", "出行", "外卖", "提醒", "几点"],
    "interests": ["游戏", "电影", "音乐", "玩", "爱好"],
    "goals": ["目标", "计划", "想做", "想要"],
}


def _route_dimensions(query: str) -> list[str]:
    """Route query to relevant dimensions based on keywords."""
    matched = ["episodic"]  # always search episodic
    for dim, kws in _DIM_ROUTING.items():
        if any(kw in query for kw in kws):
            matched.append(dim)
    # If no specific dimension matched, search all
    if len(matched) == 1:
        return DIMENSION_KEYS
    return matched


def search(query: str, top_k: int = 5) -> dict:
    """
    Main retrieval entry point.

    Returns: {
        "answer": str (composed answer or empty),
        "results": list[dict],
        "time_range": (start, end) or None,
        "episodic_timeline": list[dict] (if time query),
    }
    """
    result = {"answer": "", "results": [], "time_range": None, "episodic_timeline": []}

    # 1. Parse time range
    time_range = _parse_time(query)
    if time_range:
        result["time_range"] = time_range
        episodes = profile_store.query_time_range(*time_range)

        if episodes:
            result["episodic_timeline"] = episodes
            # If query has semantic content, search within episodes
            # Otherwise just return timeline
            clean_query = query
            for pattern, _ in _TIME_PATTERNS:
                clean_query = re.sub(pattern, "", clean_query).strip()
            if clean_query:
                # Semantic + time: search episodes content
                texts = [f"{e['ts'][:16]} {e['content']}" for e in episodes]
                result["results"] = [{"text": t, "score": 1.0, "dimension": "episodic"} for t in texts[:5]]
                result["answer"] = "\n".join(t["text"] for t in result["results"])
            else:
                # Pure time query: return timeline
                result["answer"] = "\n".join(
                    f"[{e['ts'][:16]}] {e['content']}" for e in episodes[:10]
                )
            return result

    # 2. Vague/episodic query → episodic + all dimensions
    if len(query) < 10 or any(w in query for w in ["刚刚", "之前", "前面", "上次"]):
        results = vector_store.query_all(query, top_k=min(top_k * 2, 10))
        result["results"] = results
        if results:
            result["answer"] = results[0]["text"]
        return result

    # 3. Semantic cross-dimension query
    dims = _route_dimensions(query)
    results = vector_store.query_all(query, top_k=top_k, dimensions=dims)

    # Merge with profile data if relevant
    if any(d in ["identity", "health", "preferences", "goals"] for d in dims):
        profile_data = profile_store.get_all()
        if profile_data:
            profile_text = "\n".join(f"{k}: {v[:100]}" for k, v in profile_data.items() if v)
            results.insert(0, {"text": f"[用户画像]\n{profile_text}", "score": 1.0, "dimension": "profile"})

    result["results"] = results
    if results:
        result["answer"] = results[0]["text"]
    return result
