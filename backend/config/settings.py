# Copyright (c) 2026 Nikolai Zelensky
"""Application settings read from the environment."""

import os
from collections.abc import Mapping
from dataclasses import dataclass, replace
from functools import lru_cache
from typing import Any, cast

from backend.config.env import get_bool, get_int
from backend.config.paths import PROJECT_ROOT


class ConfigError(ValueError):
    """Raised when one or more environment settings are invalid."""

    def __init__(self, errors: list[str]) -> None:
        """Initialize the error with every invalid setting."""
        self.errors = tuple(errors)
        super().__init__("Invalid configuration:\n" + "\n".join(errors))


@dataclass(frozen=True, slots=True)
class Settings:
    """Environment-backed defaults for Whisper, HTTP access, and resource limits."""

    # Whisper model and inference settings.
    WHISPER_MODEL_SIZE: str = "small"
    WHISPER_CPU_THREADS: int = 6
    WHISPER_LANGUAGE: str = "ru"
    WHISPER_BEAM_SIZE: int = 5
    WHISPER_TIMEOUT: int = 180
    WHISPER_DEVICE: str = "cpu"
    WHISPER_COMPUTE_TYPE: str = "int8"
    WHISPER_MODEL_PATH: str = ""
    WHISPER_OFFLINE: bool = False
    ENABLE_DOCS: bool = False
    LOG_LEVEL: str = "INFO"
    TEMP_DIR: str = str(PROJECT_ROOT / "tmp")

    # Authentication and resource limits.
    WHISPER_API_KEY: str = ""
    DOCUMENT_API_KEY: str = ""
    ALLOW_UNAUTHENTICATED: bool = False
    MAX_AUDIO_SIZE: int = 25 * 1024 * 1024
    MAX_AUDIO_DURATION: int = 600
    MAX_CONCURRENT_TRANSCRIPTIONS: int = 1
    MAX_WAITING_DOCUMENTS: int = 4
    MAX_WAITING_TRANSCRIPTIONS: int = 4


def load_settings(environ: Mapping[str, str]) -> Settings:
    """Build settings from an environment mapping and collect validation errors."""
    errors: list[str] = []
    defaults = Settings()

    def read_str(
        name: str, default: str, *, strip: bool = False, lower: bool = False
    ) -> str:
        value = environ.get(name, default)
        if strip:
            value = value.strip()
        return value.lower() if lower else value

    def read_bool(name: str, default: bool) -> bool:
        try:
            return get_bool(name, default, environ=environ)
        except ValueError as error:
            errors.append(str(error))
            return default

    def read_int(name: str, default: int) -> int:
        try:
            return get_int(name, str(default), environ=environ)
        except ValueError as error:
            errors.append(str(error))
            return default

    result = Settings(
        WHISPER_MODEL_SIZE=read_str("WHISPER_MODEL_SIZE", defaults.WHISPER_MODEL_SIZE),
        WHISPER_CPU_THREADS=read_int(
            "WHISPER_CPU_THREADS", defaults.WHISPER_CPU_THREADS
        ),
        WHISPER_LANGUAGE=read_str("WHISPER_LANGUAGE", defaults.WHISPER_LANGUAGE),
        WHISPER_BEAM_SIZE=read_int("WHISPER_BEAM_SIZE", defaults.WHISPER_BEAM_SIZE),
        WHISPER_TIMEOUT=read_int("WHISPER_TIMEOUT", defaults.WHISPER_TIMEOUT),
        WHISPER_DEVICE=read_str(
            "WHISPER_DEVICE", defaults.WHISPER_DEVICE, strip=True, lower=True
        ),
        WHISPER_COMPUTE_TYPE=read_str(
            "WHISPER_COMPUTE_TYPE", defaults.WHISPER_COMPUTE_TYPE, strip=True
        ),
        WHISPER_MODEL_PATH=read_str(
            "WHISPER_MODEL_PATH", defaults.WHISPER_MODEL_PATH, strip=True
        ),
        WHISPER_OFFLINE=read_bool("WHISPER_OFFLINE", defaults.WHISPER_OFFLINE),
        ENABLE_DOCS=read_bool("ENABLE_DOCS", defaults.ENABLE_DOCS),
        LOG_LEVEL=read_str("LOG_LEVEL", defaults.LOG_LEVEL),
        TEMP_DIR=read_str("BACKEND_TEMP_DIR", defaults.TEMP_DIR),
        WHISPER_API_KEY=read_str(
            "WHISPER_API_KEY", defaults.WHISPER_API_KEY, strip=True
        ),
        DOCUMENT_API_KEY=read_str(
            "DOCUMENT_API_KEY", defaults.DOCUMENT_API_KEY, strip=True
        ),
        ALLOW_UNAUTHENTICATED=read_bool(
            "ALLOW_UNAUTHENTICATED", defaults.ALLOW_UNAUTHENTICATED
        ),
        MAX_AUDIO_SIZE=read_int("MAX_AUDIO_SIZE", defaults.MAX_AUDIO_SIZE),
        MAX_AUDIO_DURATION=read_int("MAX_AUDIO_DURATION", defaults.MAX_AUDIO_DURATION),
        MAX_CONCURRENT_TRANSCRIPTIONS=read_int(
            "MAX_CONCURRENT_TRANSCRIPTIONS",
            defaults.MAX_CONCURRENT_TRANSCRIPTIONS,
        ),
        MAX_WAITING_DOCUMENTS=read_int(
            "MAX_WAITING_DOCUMENTS", defaults.MAX_WAITING_DOCUMENTS
        ),
        MAX_WAITING_TRANSCRIPTIONS=read_int(
            "MAX_WAITING_TRANSCRIPTIONS", defaults.MAX_WAITING_TRANSCRIPTIONS
        ),
    )

    if errors:
        raise ConfigError(errors)

    return result


@lru_cache(maxsize=1)
def _load_cached_settings() -> Settings:
    return load_settings(os.environ)


@dataclass(slots=True)
class _SettingsState:
    """Hold mutable state behind the settings compatibility proxy."""

    override: Settings | None = None


_settings_state = _SettingsState()


def get_settings() -> Settings:
    """Return the process-wide cached settings."""
    if _settings_state.override is not None:
        return _settings_state.override
    return _load_cached_settings()


def reset_settings_cache() -> None:
    """Clear cached settings so tests can reload a changed environment."""
    _settings_state.override = None
    _load_cached_settings.cache_clear()


def _set_setting(name: str, value: object) -> None:
    """Replace one cached field for compatibility with existing test patches."""
    if name not in Settings.__dataclass_fields__:
        raise AttributeError(name)

    updated = replace(get_settings(), **cast("Any", {name: value}))
    baseline = _load_cached_settings()
    _settings_state.override = None if updated == baseline else updated


class _SettingsProxy:
    """Resolve settings lazily while retaining legacy attribute access."""

    def __getattr__(self, name: str) -> object:
        return getattr(get_settings(), name)

    def __setattr__(self, name: str, value: object) -> None:
        _set_setting(name, value)

    def __delattr__(self, name: str) -> None:
        """Restore a setting to its cached environment value."""
        _set_setting(name, getattr(_load_cached_settings(), name))


settings: Settings = cast("Settings", _SettingsProxy())
