"""
Task engine — scheduled reminders and periodic actions.

Tasks are stored in SQLite with recurrence support.
Fires callbacks when tasks are due.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Callable, Awaitable

from .config import SQLITE_PATH
from .profile import profile_store

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════
# SQLite setup
# ═══════════════════════════════════════════════════════════════

def _get_conn():
    import sqlite3
    conn = sqlite3.connect(SQLITE_PATH, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            name       TEXT NOT NULL,
            dimension  TEXT DEFAULT 'life',
            cron_expr  TEXT,           -- '*/30 * * * *' or None for one-shot
            next_fire  TEXT NOT NULL,  -- ISO datetime
            message    TEXT,           -- what to say/send
            enabled    INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_next ON tasks(next_fire)")
    conn.commit()
    return conn


# ═══════════════════════════════════════════════════════════════
# Task CRUD
# ═══════════════════════════════════════════════════════════════

def add_task(name: str, fire_at: str, message: str = "",
             dimension: str = "life", cron: str | None = None) -> int:
    """Add a one-shot or recurring task."""
    conn = _get_conn()
    cur = conn.execute(
        "INSERT INTO tasks (name, dimension, cron_expr, next_fire, message) VALUES (?, ?, ?, ?, ?)",
        (name, dimension, cron, fire_at, message),
    )
    conn.commit()
    conn.close()
    return cur.lastrowid


def add_reminder(message: str, delay_minutes: int = 30):
    """Convenience: add a reminder N minutes from now."""
    fire_at = (datetime.now() + timedelta(minutes=delay_minutes)).strftime("%Y-%m-%d %H:%M:%S")
    return add_task("reminder", fire_at, message, dimension="life")


def get_due_tasks() -> list[dict]:
    """Get all enabled tasks that are past due."""
    conn = _get_conn()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    rows = conn.execute(
        "SELECT id, name, dimension, cron_expr, next_fire, message FROM tasks WHERE enabled=1 AND next_fire <= ?",
        (now,),
    ).fetchall()
    conn.close()
    return [
        {"id": r[0], "name": r[1], "dimension": r[2],
         "cron": r[3], "next_fire": r[4], "message": r[5]}
        for r in rows
    ]


def mark_done(task_id: int):
    """Mark a task as done — for one-shot, disable; for recurring, reschedule."""
    conn = _get_conn()
    task = conn.execute("SELECT cron_expr FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if not task:
        conn.close()
        return
    cron = task[0]
    if cron:
        # Recurring: advance next_fire by cron expression
        from croniter import croniter as _croniter
        now = datetime.now()
        cron_iter = _croniter(cron, now)
        next_time = cron_iter.get_next(datetime)
        conn.execute("UPDATE tasks SET next_fire = ? WHERE id = ?",
                     (next_time.strftime("%Y-%m-%d %H:%M:%S"), task_id))
    else:
        # One-shot: disable
        conn.execute("UPDATE tasks SET enabled = 0 WHERE id = ?", (task_id,))
    conn.commit()
    conn.close()


def list_tasks() -> list[dict]:
    conn = _get_conn()
    rows = conn.execute(
        "SELECT id, name, dimension, next_fire, message, enabled FROM tasks ORDER BY next_fire"
    ).fetchall()
    conn.close()
    return [
        {"id": r[0], "name": r[1], "dimension": r[2],
         "next_fire": r[3], "message": r[4], "enabled": bool(r[5])}
        for r in rows
    ]


# ═══════════════════════════════════════════════════════════════
# Async engine — polls for due tasks and fires callbacks
# ═══════════════════════════════════════════════════════════════

class TaskRunner:
    """Background async task that checks for due tasks every 30s."""

    def __init__(self):
        self._callbacks: list[Callable[[dict], Awaitable[None]]] = []
        self._running = False

    def on_fire(self, cb: Callable[[dict], Awaitable[None]]):
        """Register a callback for when a task is due."""
        self._callbacks.append(cb)

    async def start(self):
        self._running = True
        while self._running:
            try:
                for task in get_due_tasks():
                    logger.info("[tasks] firing: %s", task["name"])
                    for cb in self._callbacks:
                        await cb(task)
                    mark_done(task["id"])
            except Exception as e:
                logger.error("[tasks] poll error: %s", e)
            await asyncio.sleep(30)

    def stop(self):
        self._running = False


# Singleton
task_runner = TaskRunner()
