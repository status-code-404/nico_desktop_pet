"""
Local CosyVoice2-0.5B TTS — zero-shot voice cloning on CPU.

Uses the CosyVoice repo at ../../CosyVoice with bundled Matcha-TTS.
Model at data/models/cosyvoice/CosyVoice2-0.5B
Reference audio at resources/audio/nico_reference.wav

RTF: ~2.5x on Mac CPU (15s per 5s audio)
"""

from __future__ import annotations

import asyncio
import os
import sys
import tempfile
from pathlib import Path

_THIS_DIR = os.path.dirname(__file__)
_COSYVOICE_ROOT = os.path.abspath(os.path.join(_THIS_DIR, "..", "..", "..", "CosyVoice"))
_MATCHA_ROOT = os.path.join(_COSYVOICE_ROOT, "third_party", "Matcha-TTS")

sys.path.insert(0, _COSYVOICE_ROOT)
sys.path.insert(0, _MATCHA_ROOT)

import soundfile as sf
from cosyvoice.cli.cosyvoice import AutoModel

from server.config import settings

_model = None


def _get_ref_wav() -> str:
    val = settings.tts_local_reference_audio
    if val and os.path.exists(val):
        return val
    return os.path.abspath(os.path.join(_THIS_DIR, "..", "..", "..", "resources", "audio", "nico_reference.wav"))


def _get_model():
    global _model
    if _model is None:
        model_dir = os.path.join(settings.cosyvoice_model_dir, settings.tts_local_model)
        print(f"[tts:local] loading {settings.tts_local_model} from {model_dir} ...")
        _model = AutoModel(model_dir=model_dir)
        print(f"[tts:local] ready, sr={_model.sample_rate}")
    return _model


async def synthesize(
    text: str,
    *,
    output_path: str | None = None,
) -> str:
    model = _get_model()
    ref_wav = _get_ref_wav()
    loop = asyncio.get_running_loop()

    def _run():
        gen = model.inference_zero_shot(text, settings.tts_local_prompt_text, ref_wav)
        result = next(gen)
        audio = result["tts_speech"].squeeze().numpy()

        target = output_path or tempfile.mktemp(suffix=".wav", dir=settings.result_dir)
        Path(target).parent.mkdir(parents=True, exist_ok=True)
        sf.write(target, audio, model.sample_rate)
        return target

    return await loop.run_in_executor(None, _run)


async def synthesize_to_bytes(text: str) -> bytes:
    path = await synthesize(text)
    with open(path, "rb") as f:
        return f.read()
