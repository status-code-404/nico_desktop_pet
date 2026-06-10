import os
from pathlib import Path

from pydantic_settings import BaseSettings

_PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    # ── DeepSeek (primary LLM for chat) ──
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"

    # ── Anthropic / Claude (vision, multimodal analysis) ──
    anthropic_api_key: str = ""
    anthropic_base_url: str = "https://www.claudeio.top/"
    anthropic_model: str = "claude-opus-4-6"

    openai_api_key: str = ""

    # ── Server ──
    backend_host: str = "127.0.0.1"
    backend_port: int = 8000

    # ── Bundled tools ──
    @property
    def ffmpeg_path(self) -> str:
        return str(_PROJECT_ROOT / "backend" / "bin" / "ffmpeg")

    # ── Model paths (bundled in data/models/) ──
    @property
    def whisper_model_dir(self) -> str:
        return str(_PROJECT_ROOT / "data" / "models" / "whisper")

    @property
    def cosyvoice_model_dir(self) -> str:
        return str(_PROJECT_ROOT / "data" / "models" / "cosyvoice")

    # ── Data paths ──
    @property
    def data_dir(self) -> str:
        return str(_PROJECT_ROOT / "data")

    @property
    def screenshot_dir(self) -> str:
        return str(_PROJECT_ROOT / "data" / "screenshots")

    @property
    def context_dir(self) -> str:
        return str(_PROJECT_ROOT / "data" / "context_history")

    @property
    def report_dir(self) -> str:
        return str(_PROJECT_ROOT / "data" / "daily_reports")

    @property
    def voice_dir(self) -> str:
        return str(_PROJECT_ROOT / "data" / "voice_recordings")

    @property
    def result_dir(self) -> str:
        """TTS output dir: result/audio/{aliyun|local}/"""
        return str(_PROJECT_ROOT / "result" / "audio" / self.tts_provider)

    @property
    def face_encodings_dir(self) -> str:
        return str(_PROJECT_ROOT / "data" / "face_encodings")

    # ── Frontend ──
    pet_width: int = 180  # pixel width of pet window (aspect ratio 1:1)
    pet_fps: int = 24     # animation frame rate

    # ── Debug ──
    debug_voice: bool = False  # print voice transcription results

    # ── Features ──
    screenshot_interval: int = 10
    drink_reminder_hours: float = 1.5
    face_detect_interval: int = 30
    mood_refresh_interval: int = 240

    # ── Model params ──
    whisper_model_size: str = "base"
    ocr_languages: list[str] = ["ch_sim", "en"]

    # ── TTS ──
    tts_provider: str = "aliyun"  # "aliyun" | "local"

    # ── Local TTS (CosyVoice2-0.5B zero-shot) ──
    tts_local_model: str = "CosyVoice2-0.5B"  # subdir under cosyvoice_model_dir
    tts_local_prompt_text: str = "人沒辦法教令院剛少學就用我二十年研究經歷畢竟人是當下的幾合"
    tts_local_reference_audio: str = ""  # set to path or empty for default resources/audio/nico_reference.wav

    # ── Alibaba Cloud DashScope (百炼) CosyVoice API ──
    dashscope_api_key: str = ""
    cosyvoice_model: str = "cosyvoice-v3.5-flash"
    nicole_voice_id: str = ""

    # ── Context ──
    max_context_entries: int = 50
    chat_memory_enabled: bool = False
    chat_history_limit: int = 10
    chat_search_enabled: bool = True
    tavily_api_key: str = ""

    # ── TTS Performance ──
    # TTS 并发上限。阿里云免费账号 QPS≈3，超出触发 Throttling.RateQuota。
    tts_concurrency: int = 3  # 阿里云免费版QPS上限≈2
    chat_max_tokens: int = 512  # ~250 Chinese chars

    model_config = {
        "env_file": str(_PROJECT_ROOT / ".env"),
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


settings = Settings()
