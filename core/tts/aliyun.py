"""
Aliyun DashScope CosyVoice TTS — simple per-call synth, 3 concurrent max.
"""

from __future__ import annotations

import asyncio
import ssl
import time

import dashscope
from dashscope.audio.tts_v2 import (
    AudioFormat,
    SpeechSynthesizer,
    VoiceEnrollmentService,
)

from server.config import settings

import websocket as _ws
_orig = _ws.WebSocketApp.run_forever
_ws.WebSocketApp.run_forever = lambda self, *a, **kw: _orig(
    self, *a, **{**kw, "sslopt": {"cert_reqs": ssl.CERT_NONE, "check_hostname": False}})

dashscope.api_key = settings.dashscope_api_key
dashscope.base_websocket_api_url = "wss://dashscope.aliyuncs.com/api-ws/v1/inference"

DEFAULT_PRESET_VOICE = "longanyang"
RPS = 3  # max calls per second
_send_lock = asyncio.Lock()
_send_count = 0
_send_window = 0.0


async def synthesize(
    text: str,
    *,
    voice: str | None = None,
    output_path: str | None = None,
) -> str:
    global _send_count, _send_window
    import os as _os, time as _time
    import tempfile as _tempfile

    # Rate limit: max 3 sends per second
    async with _send_lock:
        now = _time.monotonic()
        if now - _send_window >= 1.0:
            _send_count = 0; _send_window = now
        if _send_count >= RPS:
            await asyncio.sleep(1.0 - (now - _send_window))
            _send_count = 0; _send_window = _time.monotonic()
        _send_count += 1

    vid = voice or settings.nicole_voice_id or DEFAULT_PRESET_VOICE
    synth = SpeechSynthesizer(
        model=settings.cosyvoice_model, voice=vid,
        format=AudioFormat.WAV_24000HZ_MONO_16BIT,
    )
    loop = asyncio.get_running_loop()
    audio = await loop.run_in_executor(None, synth.call, text)
    if audio is None:
        raise RuntimeError("Synthesis returned None")
    print(
        f"[tts] request_id={synth.get_last_request_id()}, "
        f"first_packet={synth.get_first_package_delay()}ms"
    )

    target = output_path or _tempfile.mktemp(suffix=".wav", dir=settings.result_dir)
    _os.makedirs(_os.path.dirname(target), exist_ok=True)
    with open(target, "wb") as f:
        f.write(audio)
    return target


def create_nicole_voice(audio_url: str) -> str:
    service = VoiceEnrollmentService()
    voice_id = service.create_voice(
        target_model=settings.cosyvoice_model, prefix="nicole",
        url=audio_url, language_hints=["zh"], max_prompt_audio_length=30.0,
    )
    for i in range(30):
        info = service.query_voice(voice_id=voice_id)
        s = info.get("status", "")
        if s == "OK": return voice_id
        if s in ("UNDEPLOYED", "FAILED"): raise RuntimeError(f"Failed: {info}")
        time.sleep(5)
    raise TimeoutError("Voice enrollment timed out")
