"""Application settings read from the environment."""

import os

from backend.config.env import get_bool, get_int
from backend.config.paths import PROJECT_ROOT


class Settings:
    """Environment-backed defaults for Whisper, HTTP access, and resource limits."""

    # Whisper settings previously hard-coded in app.py.
    WHISPER_MODEL_SIZE = os.getenv("WHISPER_MODEL_SIZE", "small")
    WHISPER_CPU_THREADS = get_int("WHISPER_CPU_THREADS", "6")
    WHISPER_LANGUAGE = os.getenv("WHISPER_LANGUAGE", "ru")
    WHISPER_BEAM_SIZE = get_int("WHISPER_BEAM_SIZE", "5")
    WHISPER_DEVICE = os.getenv("WHISPER_DEVICE", "cpu").strip().lower()
    WHISPER_COMPUTE_TYPE = os.getenv("WHISPER_COMPUTE_TYPE", "int8").strip()
    WHISPER_MODEL_PATH = os.getenv("WHISPER_MODEL_PATH", "").strip()
    WHISPER_OFFLINE = get_bool("WHISPER_OFFLINE", False)
    ENABLE_DOCS = get_bool("ENABLE_DOCS", False)
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    TEMP_DIR = os.getenv("BACKEND_TEMP_DIR", str(PROJECT_ROOT / "tmp"))

    # Security and resource limits introduced in delivery 1.
    WHISPER_API_KEY = os.getenv("WHISPER_API_KEY", "").strip()
    DOCUMENT_API_KEY = os.getenv("DOCUMENT_API_KEY", "").strip()
    ALLOW_UNAUTHENTICATED = get_bool("ALLOW_UNAUTHENTICATED", False)
    MAX_AUDIO_SIZE = get_int("MAX_AUDIO_SIZE", str(25 * 1024 * 1024))
    MAX_AUDIO_DURATION = get_int("MAX_AUDIO_DURATION", "600")
    MAX_CONCURRENT_TRANSCRIPTIONS = get_int("MAX_CONCURRENT_TRANSCRIPTIONS", "1")
    MAX_WAITING_DOCUMENTS = get_int("MAX_WAITING_DOCUMENTS", "4")
    MAX_WAITING_TRANSCRIPTIONS = get_int("MAX_WAITING_TRANSCRIPTIONS", "4")


settings = Settings()
