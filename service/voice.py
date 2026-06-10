"""
Voice service — STT + LLM + TTS pipeline.
Uses: core.stt.whisper, core.llm.client, core.tts.{aliyun,local}
"""

import asyncio
import os
import re

from server.config import settings
from core.llm.client import llm_client
from core.stt.whisper import transcribe_upload

TTS_CHUNK_SIZE = 40


def _tts():
    if settings.tts_provider == "local":
        from core.tts.local import synthesize
    else:
        from core.tts.aliyun import synthesize
    return synthesize


# ── Smart text splitting ──────────────────────────────────────────

def _split_text(text: str) -> list[str]:
    """40-char chunks at sentence boundaries."""
    return _split_by_size(text, TTS_CHUNK_SIZE)


async def tts(text: str):
    """Async generator: yields file paths as they complete."""
    chunks = _split_text(text)
    synthesize = _tts()
    tasks = [asyncio.create_task(synthesize(c)) for c in chunks]
    for task in tasks:
        yield await task


async def tts_all(text: str) -> list[str]:
    """Non-streaming TTS — returns all files at once."""
    return [f async for f in tts(text)]


def _split_by_size(text: str, size: int, max_parts: int = 99) -> list[str]:
    """Hard-split by char count, adjusting to nearest sentence boundary."""
    chunks = []
    start = 0
    total = len(text)

    while start < total:
        if len(chunks) >= max_parts - 1:
            chunks.append(text[start:].strip())
            break

        end = start + size
        if end >= total:
            chunks.append(text[start:].strip())
            break

        # Search backward for sentence break
        for ch in "。！？\n！？.":
            idx = text.rfind(ch, start, end)
            if idx > start + size // 2:
                end = idx + 1
                break

        chunks.append(text[start:end].strip())
        start = end

    return chunks or [text]


# ── Public API ────────────────────────────────────────────────────

async def transcribe(upload_file) -> dict:
    return await transcribe_upload(upload_file)


async def chat(upload_file) -> str:
    r = await transcribe_upload(upload_file)
    text = r.get("text", "")
    return await llm_client.chat(text) if text else "主人说了什么？我没听清楚呢…"


async def chat_audio(upload_file) -> str:
    reply = await chat(upload_file)
    return await tts(reply)
