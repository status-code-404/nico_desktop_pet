"""
Voice service — STT + LLM + TTS pipeline.
Uses: core.stt.whisper, core.llm.client, core.tts.{aliyun,local,volcengine}
"""

import asyncio
import os
import re

from server.config import settings
from core.llm.client import llm_client
from core.stt.whisper import transcribe_upload


def _record_conversation(user_text: str, reply_text: str):
    """Non-blocking wrapper for memory collection."""
    try:
        from core.memory import collector
        collector.record("user", user_text)
        collector.record("assistant", reply_text)
    except Exception:
        pass

TTS_CHUNK_SIZE = 40
DUPLEX_FLUSH_CHARS = 30  # flush to TTS after this many chars accumulated


def _tts():
    if settings.tts_provider == "local":
        from core.tts.local import synthesize
    elif settings.tts_provider == "volcengine":
        from core.tts.volcengine import synthesize
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
    if settings.stt_provider == "volcengine":
        return await _transcribe_volcengine(upload_file)
    return await transcribe_upload(upload_file)


async def _transcribe_volcengine(upload_file) -> dict:
    """Transcribe via Volcengine streaming ASR."""
    import wave, io
    from core.stt.volcengine_asr import transcribe_bytes

    content = await upload_file.read()
    with wave.open(io.BytesIO(content), "rb") as wf:
        pcm = wf.readframes(wf.getnframes())

    text = await transcribe_bytes(pcm)
    return {"text": text.strip(), "language": "zh", "duration_s": 0}


async def chat(upload_file) -> str:
    r = await transcribe_upload(upload_file)
    text = r.get("text", "")
    return await llm_client.chat(text) if text else "主人说了什么？我没听清楚呢…"


async def chat_audio(upload_file) -> str:
    reply = await chat(upload_file)
    return await tts(reply)


async def chat_audio_stream(upload_file, *, provider: str | None = None):
    """
    全链路流式: STT → LLM stream → 双工 TTS.

    音频转文字后，LLM 逐 token 输出，攒够一句就送 TTS 合成，
    音频即时 yield 出去。首音延迟 = STT + LLM首token + TTS首chunk.
    """
    tts_provider = provider or settings.tts_provider

    # 1. STT
    r = await transcribe_upload(upload_file)
    text = r.get("text", "")
    if not text:
        return  # empty — no response needed

    if tts_provider != "volcengine":
        # Fallback: old pipeline (LLM full → TTS chunked)
        reply = await llm_client.chat(text)
        async for path in tts(reply):
            yield f"file:{path}"
        return

    # 2. Volcengine duplex: LLM stream → sentence buffer → TTS duplex
    from core.tts.volcengine import duplex_stream

    # Build an async generator that buffers LLM tokens into sentences
    async def sentence_chunks():
        """Buffer LLM tokens, yield sentences when ready."""
        buf = ""
        async for token in llm_client.chat_stream(text):
            buf += token
            # Flush on sentence boundary or max chars
            if buf and (token in "。！？\n" or len(buf) >= DUPLEX_FLUSH_CHARS):
                yield buf
                buf = ""
        if buf.strip():
            yield buf

    async for audio_chunk in duplex_stream(sentence_chunks()):
        yield audio_chunk


async def tts_stream_from_text(user_text: str):
    """
    文本 → LLM 流式 + 双工 TTS → 即时音频流 (async generator).

    真正的并发: LLM 边出字边送 TTS，不等全文。首句到即合成。
    返回: 纯音频 bytes 流，无文本.
    """
    tts_provider = settings.tts_provider

    if tts_provider != "volcengine":
        reply = await llm_client.chat(user_text)
        async for path in tts(reply):
            yield f"file:{path}"
        return

    from core.tts.volcengine import duplex_stream

    reply_text = [""]
    sentence_queue: asyncio.Queue[str | None] = asyncio.Queue()

    async def llm_reader():
        buf = ""
        try:
            async for token in llm_client.chat_stream(user_text):
                reply_text[0] += token
                buf += token
                if token in "。！？\n" or len(buf) >= DUPLEX_FLUSH_CHARS:
                    await sentence_queue.put(buf)
                    buf = ""
            if buf.strip():
                await sentence_queue.put(buf)
        finally:
            await sentence_queue.put(None)
            # Fire-and-forget: background record to memory (zero overhead)
            if reply_text[0].strip():
                import asyncio as _aio
                _aio.create_task(_aio.to_thread(
                    _record_conversation, user_text, reply_text[0]))

    async def sentence_feeder():
        while True:
            s = await sentence_queue.get()
            if s is None:
                break
            yield s

    # Start LLM reader — sentences will be ready by the time duplex needs them
    asyncio.create_task(llm_reader())

    async for audio in duplex_stream(sentence_feeder()):
        yield audio
