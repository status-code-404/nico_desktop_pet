"""
User profile — SQLite store for structured identity / dimension facts.

Operations: upsert (replace), get (read), delete.
Not for free-text — that goes to ChromaDB per-dimension collections.
"""

from __future__ import annotations

import sqlite3
import json
import logging
from typing import Any

from .config import SQLITE_PATH, PROFILE_FIELDS

logger = logging.getLogger(__name__)


class ProfileStore:
    """SQLite-backed user profile with upsert semantics."""

    def __init__(self):
        self._conn = sqlite3.connect(SQLITE_PATH, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._init_table()

    def _init_table(self):
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS profile (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT DEFAULT (datetime('now'))
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS episodic_timeline (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                ts        TEXT DEFAULT (datetime('now')),
                source    TEXT,      -- 'user', 'assistant', 'system'
                content   TEXT,      -- the actual message/action
                dimensions TEXT,     -- JSON array of dimension keys
                metadata  TEXT       -- JSON extra info
            )
        """)
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_ep_ts ON episodic_timeline(ts)")
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_ep_dim ON episodic_timeline(dimensions)")
        self._conn.commit()

    # ── Profile CRUD ──────────────────────────────────────────

    def upsert(self, key: str, value: str | dict | list) -> None:
        """Insert or replace a profile field."""
        if isinstance(value, (dict, list)):
            value = json.dumps(value, ensure_ascii=False)
        self._conn.execute(
            "INSERT OR REPLACE INTO profile (key, value, updated_at) VALUES (?, ?, datetime('now'))",
            (key, value),
        )
        self._conn.commit()

    def get(self, key: str) -> str | None:
        row = self._conn.execute("SELECT value FROM profile WHERE key = ?", (key,)).fetchone()
        return row[0] if row else None

    def get_all(self) -> dict[str, str]:
        rows = self._conn.execute("SELECT key, value FROM profile").fetchall()
        return {k: v for k, v in rows}

    def delete(self, key: str) -> None:
        self._conn.execute("DELETE FROM profile WHERE key = ?", (key,))
        self._conn.commit()

    def upsert_batch(self, updates: dict[str, str]) -> None:
        for k, v in updates.items():
            self.upsert(k, v)

    # ── Episodic timeline ─────────────────────────────────────

    def add_episode(self, source: str, content: str,
                     dimensions: list[str] | None = None,
                     metadata: dict | None = None) -> int:
        """Record an event in the episodic timeline. Returns row id."""
        dims = json.dumps(dimensions or ["episodic"], ensure_ascii=False)
        meta = json.dumps(metadata or {}, ensure_ascii=False)
        cur = self._conn.execute(
            "INSERT INTO episodic_timeline (source, content, dimensions, metadata) VALUES (?, ?, ?, ?)",
            (source, content, dims, meta),
        )
        self._conn.commit()
        return cur.lastrowid

    def query_time_range(self, start: str, end: str,
                          source: str | None = None) -> list[dict]:
        """Get episodes within a time range."""
        query = "SELECT id, ts, source, content, dimensions, metadata FROM episodic_timeline WHERE ts BETWEEN ? AND ?"
        params = [start, end]
        if source:
            query += " AND source = ?"
            params.append(source)
        query += " ORDER BY ts DESC LIMIT 100"
        rows = self._conn.execute(query, params).fetchall()
        return [
            {
                "id": r[0], "ts": r[1], "source": r[2],
                "content": r[3], "dimensions": json.loads(r[4]),
                "metadata": json.loads(r[5]) if r[5] else {},
            }
            for r in rows
        ]

    def query_recent(self, limit: int = 50) -> list[dict]:
        rows = self._conn.execute(
            "SELECT id, ts, source, content, dimensions, metadata FROM episodic_timeline ORDER BY ts DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [
            {
                "id": r[0], "ts": r[1], "source": r[2],
                "content": r[3], "dimensions": json.loads(r[4]),
                "metadata": json.loads(r[5]) if r[5] else {},
            }
            for r in rows
        ]

    def close(self):
        self._conn.close()


# Singleton
profile_store = ProfileStore()
