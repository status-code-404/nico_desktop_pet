"""
Volcengine (豆包) 流式语音识别 — bigmodel streaming ASR.

协议: 与 TTS 相同的 4-byte binary framing.
端点: wss://openspeech.bytedance.com/api/v3/sauc/bigmodel_async
鉴权: X-Api-Key (新版控制台) + X-Api-Sequence: -1
"""

from __future__ import annotations

import asyncio
import contextlib
import gzip
import io
import json
import logging
import ssl
import struct
import uuid
from collections.abc import AsyncIterator
from enum import IntEnum

import websockets

from server.config import settings

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════════

WS_URL = "wss://openspeech.bytedance.com/api/v3/sauc/bigmodel_async"
RESOURCE_ID = "volc.seedasr.sauc.duration"

_SSL = ssl.create_default_context()
_SSL.check_hostname = False
_SSL.verify_mode = ssl.CERT_NONE


class MsgType(IntEnum):
    FullClientRequest = 0b0001
    AudioOnlyClient = 0b0010
    FullServerResponse = 0b1001
    Error = 0b1111


class Flags(IntEnum):
    NoSeq = 0b0000
    PositiveSeq = 0b0001
    LastNoSeq = 0b0010
    NegativeSeq = 0b0011


class Serial(IntEnum):
    Raw = 0b0000
    JSON = 0b0001


class Compress(IntEnum):
    None_ = 0b0000
    Gzip = 0b0001


# ═══════════════════════════════════════════════════════════════
# Message
# ═══════════════════════════════════════════════════════════════

class Message:
    """Binary protocol frame with marshal/unmarshal."""

    __slots__ = ("type", "flag", "serial", "compress", "seq", "payload")

    def __init__(
        self,
        type: MsgType,
        flag: Flags = Flags.NoSeq,
        serial: Serial = Serial.JSON,
        compress: Compress = Compress.None_,
        seq: int = 0,
        payload: bytes = b"",
    ):
        self.type = type
        self.flag = flag
        self.serial = serial
        self.compress = compress
        self.seq = seq
        self.payload = payload

    def marshal(self) -> bytes:
        """Serialize to bytes: 4B header + [seq?] + 4B len + payload."""
        buf = io.BytesIO()
        buf.write(bytes([
            (1 << 4) | 1,  # version=1, header_size=1
            (int(self.type) << 4) | int(self.flag),
            (int(self.serial) << 4) | int(self.compress),
            0x00,
        ]))

        # Sequence field (uses doubao-speech convention: always include seq)
        if self.flag in (Flags.PositiveSeq, Flags.NegativeSeq):
            buf.write(struct.pack(">i", self.seq))

        buf.write(struct.pack(">I", len(self.payload)))
        if self.payload:
            buf.write(self.payload)
        return buf.getvalue()

    @classmethod
    def unmarshal(cls, data: bytes) -> Message:
        """Deserialize from bytes."""
        if len(data) < 4:
            raise ValueError(f"frame too short: {len(data)}B")
        header_size = (data[0] & 0x0F) * 4
        msg = cls(
            type=MsgType(data[1] >> 4),
            flag=Flags(data[1] & 0x0F),
            serial=Serial(data[2] >> 4),
            compress=Compress(data[2] & 0x0F),
        )
        pos = header_size

        if msg.flag in (Flags.PositiveSeq, Flags.NegativeSeq):
            msg.seq = struct.unpack(">i", data[pos:pos + 4])[0]
            pos += 4

        if pos + 4 <= len(data):
            plen = struct.unpack(">I", data[pos:pos + 4])[0]
            pos += 4
            if plen and pos + plen <= len(data):
                msg.payload = data[pos:pos + plen]
        return msg

    def json(self) -> dict | None:
        """Parse payload as JSON (handles gzip)."""
        if not self.payload:
            return None
        raw = self.payload
        if self.compress == Compress.Gzip:
            try:
                raw = gzip.decompress(raw)
            except Exception:
                return None
        try:
            return json.loads(raw.decode("utf-8"))
        except Exception:
            return None


# ═══════════════════════════════════════════════════════════════
# Streaming ASR
# ═══════════════════════════════════════════════════════════════

async def transcribe_stream(
    audio_chunks: AsyncIterator[bytes],
) -> AsyncIterator[str]:
    """
    流式 ASR: 音频 chunk 流入 → 识别文本流出.
    audio_chunks: PCM16 16kHz mono 音频，每块 ~200ms (6400 bytes).
    """

    api_key = settings.volcengine_asr_api_key
    uid = str(uuid.uuid4())

    init_payload = gzip.compress(json.dumps({
        "user": {"uid": uid},
        "audio": {"format": "pcm", "rate": 16000, "bits": 16, "channel": 1},
        "request": {
            "model_name": "bigmodel",
            "enable_itn": True, "enable_punc": True, "enable_ddc": True,
        },
    }).encode())

    print(f"[volc-asr] connecting (uid={uid})")

    async with websockets.connect(
        WS_URL, ssl=_SSL,
        additional_headers={
            "X-Api-Key": api_key,
            "X-Api-Resource-Id": RESOURCE_ID,
            "X-Api-Request-Id": uid,
            "X-Api-Sequence": "-1",
        },
        max_size=4 * 1024 * 1024,
        open_timeout=15,
    ) as ws:

        # 1. Init: FullClientRequest + await server ack
        await ws.send(Message(
            type=MsgType.FullClientRequest, flag=Flags.PositiveSeq,
            serial=Serial.JSON, compress=Compress.Gzip,
            seq=1, payload=init_payload,
        ).marshal())

        ack_raw = await asyncio.wait_for(ws.recv(), timeout=15)
        ack = Message.unmarshal(ack_raw)
        print(f"[volc-asr] init ack type={ack.type.name} flag={ack.flag.name} seq={ack.seq} payload_len={len(ack.payload)}")
        print(f"[volc-asr] init ack json: {ack.json()}")

        # 2. Concurrent: send audio + receive results
        text_queue: asyncio.Queue[str | None] = asyncio.Queue()
        sender_done = asyncio.Event()

        async def sender():
            seq = 2
            try:
                async for raw in audio_chunks:
                    await ws.send(Message(
                        type=MsgType.AudioOnlyClient, flag=Flags.PositiveSeq,
                        compress=Compress.Gzip,
                        seq=seq, payload=gzip.compress(raw),
                    ).marshal())
                    seq += 1
            except Exception as e:
                logger.error("[volc-asr] send err: %s", e)
            finally:
                # Last (negative) packet
                try:
                    await ws.send(Message(
                        type=MsgType.AudioOnlyClient, flag=Flags.NegativeSeq,
                        compress=Compress.Gzip,
                        seq=-(seq), payload=gzip.compress(b""),
                    ).marshal())
                except Exception:
                    pass
                sender_done.set()

        async def receiver():
            recv_count = 0
            try:
                while True:
                    try:
                        raw = await asyncio.wait_for(ws.recv(), timeout=30)
                    except asyncio.TimeoutError:
                        print("[volc-asr] recv timeout, breaking")
                        break
                    msg = Message.unmarshal(raw)
                    recv_count += 1
                    if msg.type == MsgType.FullServerResponse:
                        body = msg.json()
                        if body:
                            text = body.get("result", {}).get("text", "")
                            if text:
                                print(f"[volc-asr] #{recv_count} text: {text!r}")
                                await text_queue.put(text)
                            else:
                                print(f"[volc-asr] #{recv_count} no text in: {json.dumps(body, ensure_ascii=False)[:100]}")
                        else:
                            print(f"[volc-asr] #{recv_count} no json body")
                    else:
                        print(f"[volc-asr] #{recv_count} type={msg.type.name if hasattr(msg.type, 'name') else msg.type}")
            except websockets.exceptions.ConnectionClosed as e:
                print(f"[volc-asr] ws closed after {recv_count} responses: {e}")
            except Exception as e:
                print(f"[volc-asr] recv err after {recv_count} responses: {e}")
            finally:
                await text_queue.put(None)

        send_task = asyncio.create_task(sender())
        recv_task = asyncio.create_task(receiver())

        last = ""
        try:
            while True:
                t = await text_queue.get()
                if t is None:
                    break
                if t != last:
                    yield t
                    last = t
        finally:
            for task in (send_task, recv_task):
                if not task.done():
                    task.cancel()
            for task in (send_task, recv_task):
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await task

    logger.info("[volc-asr] done: %r", last[:60] if last else "")


# ═══════════════════════════════════════════════════════════════
# Convenience
# ═══════════════════════════════════════════════════════════════

async def transcribe_bytes(audio_data: bytes) -> str:
    """Transcribe full PCM16 audio buffer (non-streaming convenience)."""
    chunk_size = 32000  # ~1s @ 16kHz mono 16-bit — fewer chunks, faster
    final = ""

    async def chunked():
        for i in range(0, len(audio_data), chunk_size):
            yield audio_data[i:i + chunk_size]

    async for text in transcribe_stream(chunked()):
        final = text
    return final.strip()
