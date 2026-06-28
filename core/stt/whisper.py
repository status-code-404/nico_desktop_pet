"""
Whisper STT — openai-whisper (local model, bundled ffmpeg).
"""

import asyncio
import os
import ssl
import tempfile
from pathlib import Path

import whisper

from server.config import settings

ssl._create_default_https_context = ssl._create_unverified_context

_ffmpeg_dir = os.path.dirname(settings.ffmpeg_path)
if os.path.exists(settings.ffmpeg_path):
    os.environ["PATH"] = _ffmpeg_dir + os.pathsep + os.environ.get("PATH", "")

_stt_model: whisper.Whisper | None = None
_stt_size: str | None = None


def get_model() -> whisper.Whisper:
    global _stt_model, _stt_size
    size = settings.whisper_model_size
    if _stt_model is None or _stt_size != size:
        model_dir = settings.whisper_model_dir
        print(f"[whisper] loading '{size}' from {model_dir} ...")
        _stt_model = whisper.load_model(size, download_root=model_dir)
        _stt_size = size
        print(f"[whisper] ready, device={_stt_model.device}")
    return _stt_model


async def transcribe(audio_path: str, language: str | None = None) -> dict:
    model = get_model()
    kwargs = {"language": language} if language else {}
    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(None, lambda: model.transcribe(audio_path, **kwargs))
    return {
        "text": result["text"].strip(),
        "language": result.get("language", "unknown"),
        "duration_s": round(
            sum(s.get("end", 0) - s.get("start", 0) for s in result.get("segments", [])), 1
        ),
    }


async def save_upload(upload_file, target_dir: str | None = None) -> str:
    if target_dir is None:
        target_dir = settings.voice_dir
    Path(target_dir).mkdir(parents=True, exist_ok=True)
    suffix = Path(upload_file.filename).suffix if upload_file.filename else ".wav"
    fd, path = tempfile.mkstemp(suffix=suffix, dir=target_dir)
    os.close(fd)
    content = await upload_file.read()
    with open(path, "wb") as f:
        f.write(content)
    return path


def preload():
    """Pre-load Whisper model at startup (saves 1-2s on first request)."""
    get_model()


async def transcribe_upload(upload_file, language: str | None = None) -> dict:
    audio_path = await save_upload(upload_file)
    result = await transcribe(audio_path, language=language)
    result["audio_path"] = audio_path
    return result
