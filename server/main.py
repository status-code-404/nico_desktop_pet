"""
Desktop Pet Nicole — Server entry point.
"""

import os, sys, threading, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from server.config import settings
from server.routes import router


def _cleanup_audio():
    """Background thread: delete TTS audio files older than 10 min."""
    while True:
        try:
            audio_dir = os.path.join(settings.data_dir, "..", "result", "audio")
            if os.path.isdir(audio_dir):
                now = time.time()
                for root, _, files in os.walk(audio_dir):
                    for f in files:
                        if f.startswith("tmp") and f.endswith(".wav"):
                            path = os.path.join(root, f)
                            if now - os.path.getmtime(path) > 600:
                                try: os.unlink(path)
                                except OSError: pass
        except Exception:
            pass
        time.sleep(120)  # check every 2 min


_cleanup_thread = threading.Thread(target=_cleanup_audio, daemon=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"[nicole] server starting on {settings.backend_host}:{settings.backend_port}")
    print(f"[nicole] LLM    = {settings.deepseek_model} @ {settings.deepseek_base_url}")
    print(f"[nicole] Whisper = {settings.whisper_model_size}")
    _cleanup_thread.start()
    yield
    print("[nicole] shutting down")

app = FastAPI(title="Desktop Pet Nicole", version="0.2.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])

app.include_router(router)

@app.get("/api/v1/health")
async def health():
    return {"status": "ok", "service": "nicole-backend", "version": "0.2.0"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server.main:app", host=settings.backend_host, port=settings.backend_port, reload=True)
