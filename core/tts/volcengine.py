"""
Volcengine (豆包) SeedTTS 双向流式语音合成.

协议: WebSocket binary framing (wss://openspeech.bytedance.com/api/v3/tts/bidirection)
格式: 4-byte header + event(4B) + [session_id] + payload_len(4B) + payload
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import ssl
import struct
import uuid
from typing import AsyncIterator

import websockets
from websockets.asyncio.client import ClientConnection

from server.config import settings

logger = logging.getLogger(__name__)

WS_URL = "wss://openspeech.bytedance.com/api/v3/tts/bidirection"

_SSL_CONTEXT = ssl.create_default_context()
_SSL_CONTEXT.check_hostname = False
_SSL_CONTEXT.verify_mode = ssl.CERT_NONE

# ── Protocol constants ──────────────────────────────────────────────

class _Event:
    StartConnection = 1
    FinishConnection = 2
    ConnectionStarted = 50
    ConnectionFailed = 51
    ConnectionFinished = 52
    StartSession = 100
    FinishSession = 102
    SessionStarted = 150
    SessionFinished = 152
    SessionFailed = 153
    TaskRequest = 200
    TTSSentenceStart = 350
    TTSSentenceEnd = 351
    TTSResponse = 352
    TTSEnded = 359

_CONNECTION_EVENTS = frozenset({
    _Event.StartConnection, _Event.FinishConnection,
    _Event.ConnectionStarted, _Event.ConnectionFailed, _Event.ConnectionFinished,
})


def _marshal(event: int, payload: bytes, *, session_id: str = "") -> bytes:
    """Build a binary frame."""
    buf = bytearray()
    # 4-byte protocol header
    buf.append((1 << 4) | 1)   # version=1, header_size=1 (4 bytes)
    buf.append((0b0001 << 4) | 0b0100)  # FullClientRequest | WithEvent
    buf.append((0b0001 << 4) | 0b0000)  # JSON | no compression
    buf.append(0x00)             # reserved

    # event (signed int32 BE)
    buf.extend(struct.pack(">i", event))

    # session_id (skipped for connection-level events)
    if event not in _CONNECTION_EVENTS and session_id:
        sid = session_id.encode()
        buf.extend(struct.pack(">I", len(sid)))
        buf.extend(sid)

    # payload
    buf.extend(struct.pack(">I", len(payload)))
    buf.extend(payload)
    return bytes(buf)


def _unmarshal(data: bytes) -> dict:
    """Parse a binary frame into a dict for debugging."""
    if len(data) < 4:
        return {}
    header_size = (data[0] & 0x0F) * 4
    msg_type = data[1] >> 4
    flag = data[1] & 0x0F
    result = {"msg_type": msg_type, "flag": flag}
    pos = header_size

    if flag == 0x04:  # WithEvent
        result["event"] = struct.unpack(">i", data[pos:pos + 4])[0]
        pos += 4
        if result["event"] not in _CONNECTION_EVENTS:
            sid_len = struct.unpack(">I", data[pos:pos + 4])[0]
            pos += 4
            if sid_len:
                result["session_id"] = data[pos:pos + sid_len].decode(errors="replace")
                pos += sid_len

    if pos + 4 <= len(data):
        payload_len = struct.unpack(">I", data[pos:pos + 4])[0]
        pos += 4
        if payload_len and pos + payload_len <= len(data):
            result["payload"] = data[pos:pos + payload_len]
    return result


def _build_req_params() -> dict:
    """Build the req_params dict for StartSession / TaskRequest."""
    return {
        "speaker": settings.volcengine_tts_speaker,
        "audio_params": {
            "format": settings.volcengine_tts_format,
            "sample_rate": settings.volcengine_tts_sample_rate,
        },
    }


# ── Public API ──────────────────────────────────────────────────────

async def synthesize_stream(text: str) -> AsyncIterator[bytes]:
    """
    单工流式: 发送全文 → 流式接收音频 chunk.

    Yields:
        bytes: MP3/PCM 音频片段，可直接拼接成完整音频文件.
    """
    speaker = settings.volcengine_tts_speaker
    session_id = uuid.uuid4().hex
    req_params = _build_req_params()
    uid = str(uuid.uuid4())

    logger.info("[volcengine] connecting (session=%s speaker=%s)", session_id, speaker)

    async with websockets.connect(
        WS_URL,
        ssl=_SSL_CONTEXT,
        additional_headers={
            "X-Api-Key": settings.volcengine_tts_api_key,
            "X-Api-Resource-Id": settings.volcengine_tts_resource_id,
        },
    ) as ws:

        # 1. StartConnection
        await ws.send(_marshal(_Event.StartConnection, b"{}"))
        raw = await asyncio.wait_for(ws.recv(), timeout=15)
        frame = _unmarshal(raw)
        if frame.get("event") == _Event.ConnectionFailed:
            _raise_error(raw)
        if frame.get("event") != _Event.ConnectionStarted:
            raise RuntimeError(f"Expected ConnectionStarted, got {frame}")

        # 2. StartSession
        start_payload = json.dumps({
            "user": {"uid": uid},
            "namespace": "BidirectionalTTS",
            "req_params": req_params,
            "event": _Event.StartSession,
        }, ensure_ascii=False).encode()
        await ws.send(_marshal(_Event.StartSession, start_payload, session_id=session_id))

        raw = await asyncio.wait_for(ws.recv(), timeout=15)
        frame = _unmarshal(raw)
        if frame.get("event") == _Event.SessionFailed:
            _raise_error(raw)
        if frame.get("event") != _Event.SessionStarted:
            raise RuntimeError(f"Expected SessionStarted, got {frame}")

        # 3. TaskRequest
        task_payload = json.dumps({
            "user": {"uid": uid},
            "namespace": "BidirectionalTTS",
            "req_params": {**req_params, "text": text},
            "event": _Event.TaskRequest,
        }, ensure_ascii=False).encode()
        await ws.send(_marshal(_Event.TaskRequest, task_payload, session_id=session_id))

        # 4. FinishSession (signal no more text)
        await ws.send(_marshal(_Event.FinishSession, b"{}", session_id=session_id))

        # 5. Receive audio
        audio_bytes = 0
        while True:
            raw = await asyncio.wait_for(ws.recv(), timeout=30)
            frame = _unmarshal(raw)
            event = frame.get("event")
            payload = frame.get("payload", b"")

            # AudioOnlyServer (0xb) frames carry audio data
            if frame.get("msg_type") == 0xb and payload:
                yield payload
                audio_bytes += len(payload)
                continue

            if event in (_Event.SessionFinished, _Event.TTSEnded):
                break

        logger.info("[volcengine] stream done: %d audio bytes", audio_bytes)

        # 6. FinishConnection
        await ws.send(_marshal(_Event.FinishConnection, b"{}"))
        try:
            await asyncio.wait_for(ws.recv(), timeout=10)
        except asyncio.TimeoutError:
            pass


async def duplex_stream(text_chunks: AsyncIterator[str]) -> AsyncIterator[bytes]:
    """
    双工流式: LLM 边出字边送 TTS，音频即时返回.

    text_chunks: AsyncIterator[str] — LLM 流式输出的文本片段（逐句或逐段）
    Yields: bytes — MP3 音频片段，可以边接收边播放
    """
    speaker = settings.volcengine_tts_speaker
    session_id = uuid.uuid4().hex
    req_params = _build_req_params()
    uid = str(uuid.uuid4())

    logger.info("[volcengine] duplex connecting (session=%s speaker=%s)", session_id, speaker)

    async with websockets.connect(
        WS_URL,
        ssl=_SSL_CONTEXT,
        additional_headers={
            "X-Api-Key": settings.volcengine_tts_api_key,
            "X-Api-Resource-Id": settings.volcengine_tts_resource_id,
        },
    ) as ws:
        # 1. StartConnection
        await ws.send(_marshal(_Event.StartConnection, b"{}"))
        raw = await asyncio.wait_for(ws.recv(), timeout=15)
        frame = _unmarshal(raw)
        if frame.get("event") != _Event.ConnectionStarted:
            _raise_error(raw)

        # 2. StartSession
        start_payload = json.dumps({
            "user": {"uid": uid},
            "namespace": "BidirectionalTTS",
            "req_params": req_params,
            "event": _Event.StartSession,
        }, ensure_ascii=False).encode()
        await ws.send(_marshal(_Event.StartSession, start_payload, session_id=session_id))

        raw = await asyncio.wait_for(ws.recv(), timeout=15)
        frame = _unmarshal(raw)
        if frame.get("event") != _Event.SessionStarted:
            _raise_error(raw)

        # 3. Concurrent send / receive
        audio_queue: asyncio.Queue[bytes | None] = asyncio.Queue()
        send_done = asyncio.Event()

        async def sender():
            """Feed text chunks as TaskRequests, then FinishSession."""
            try:
                async for chunk in text_chunks:
                    if not chunk.strip():
                        continue
                    task_payload = json.dumps({
                        "user": {"uid": uid},
                        "namespace": "BidirectionalTTS",
                        "req_params": {**req_params, "text": chunk.strip()},
                        "event": _Event.TaskRequest,
                    }, ensure_ascii=False).encode()
                    await ws.send(_marshal(_Event.TaskRequest, task_payload, session_id=session_id))
                    logger.debug("[volcengine] duplex sent: %d chars", len(chunk.strip()))
            except Exception as e:
                logger.error("[volcengine] duplex sender error: %s", e)
            finally:
                # Signal no more text
                try:
                    await ws.send(_marshal(_Event.FinishSession, b"{}", session_id=session_id))
                except Exception:
                    pass
                send_done.set()

        async def receiver():
            """Read audio + events from server."""
            try:
                while True:
                    try:
                        raw = await asyncio.wait_for(ws.recv(), timeout=60)
                    except TimeoutError:
                        logger.warning("[volcengine] duplex recv timeout")
                        break
                    frame = _unmarshal(raw)
                    event = frame.get("event")
                    payload = frame.get("payload", b"")

                    # Audio: AudioOnlyServer (0xb) frames
                    if frame.get("msg_type") == 0xb and payload:
                        await audio_queue.put(payload)
                        continue

                    if event == _Event.SessionFinished:
                        break
                    if event == _Event.SessionFailed:
                        logger.error("[volcengine] SessionFailed")
                        break
            except websockets.exceptions.ConnectionClosed:
                logger.info("[volcengine] duplex ws closed by server")
            except Exception as e:
                logger.error("[volcengine] duplex recv error: %s", e)
            finally:
                await audio_queue.put(None)  # signal end

        recv_task = asyncio.create_task(receiver())
        send_task = asyncio.create_task(sender())

        # Yield audio as it arrives
        try:
            while True:
                chunk = await audio_queue.get()
                if chunk is None:
                    break
                yield chunk
        finally:
            # Cancel sender/receiver
            for t in (send_task, recv_task):
                if not t.done():
                    t.cancel()
            for t in (send_task, recv_task):
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await t

            # 6. FinishConnection
            try:
                await ws.send(_marshal(_Event.FinishConnection, b"{}"))
                await asyncio.wait_for(ws.recv(), timeout=10)
            except Exception:
                pass

    logger.info("[volcengine] duplex complete")

async def synthesize(text: str, output_path: str | None = None) -> str:
    """
    单工模式: 发送全文 → 收集所有音频 → 写入文件.

    Returns:
        str: 输出音频文件路径.
    """
    import os
    import tempfile

    ext = settings.volcengine_tts_format
    target = output_path or tempfile.mktemp(suffix=f".{ext}", dir=settings.result_dir)
    os.makedirs(os.path.dirname(target), exist_ok=True)

    with open(target, "wb") as f:
        async for chunk in synthesize_stream(text):
            f.write(chunk)

    size = os.path.getsize(target)
    logger.info("[volcengine] synthesized %d chars → %s (%d bytes)", len(text), target, size)
    return target



def _raise_error(raw: bytes) -> None:
    """Try to extract error info from a failed frame."""
    frame = _unmarshal(raw)
    payload = frame.get("payload", b"")
    try:
        msg = json.loads(payload)
    except Exception:
        msg = payload.decode(errors="replace") if payload else str(frame)
    raise RuntimeError(f"Volcengine TTS error: {msg}")
