# Copyright (c) 2026 Nikolai Zelensky
"""Lifecycle holder for the process-wide Whisper model."""

import logging
from collections.abc import Iterable
from importlib import import_module
from typing import Protocol, cast

from backend.config import settings

logger = logging.getLogger(__name__)


class _WhisperModelNotLoadedError(RuntimeError):
    """Raised when the Whisper model has not been initialized."""

    def __init__(self) -> None:
        """Initialize the model state error."""
        super().__init__("Whisper model is not loaded")


class _TranscriptionSegment(Protocol):
    """Expose the segment data consumed by the transcription service."""

    text: str


class _TranscriptionInfo(Protocol):
    """Expose the metadata consumed by the transcription service."""

    duration: float
    language: str | None


class _WhisperModel(Protocol):
    """Expose the Whisper model operation used by the application."""

    def transcribe(
        self,
        audio: str,
        *,
        language: str | None,
        beam_size: int,
        vad_filter: bool,
    ) -> tuple[Iterable[_TranscriptionSegment], _TranscriptionInfo]:
        """Return the generated segments and associated metadata."""
        ...


def _build_model() -> _WhisperModel:
    """Construct Whisper lazily so API modules remain importable without the extra."""
    whisper_model_factory = import_module("faster_whisper").WhisperModel

    model_path = settings.WHISPER_MODEL_PATH or settings.WHISPER_MODEL_SIZE
    return cast(
        "_WhisperModel",
        whisper_model_factory(
            model_path,
            device=settings.WHISPER_DEVICE,
            compute_type=settings.WHISPER_COMPUTE_TYPE,
            cpu_threads=settings.WHISPER_CPU_THREADS,
            local_files_only=settings.WHISPER_OFFLINE,
        ),
    )


class ModelHolder:
    """Owns the single Whisper model instance for this application process."""

    def __init__(self) -> None:
        """Initialize an empty model holder."""
        self._model: _WhisperModel | None = None

    @property
    def is_loaded(self) -> bool:
        """Return whether the Whisper model has been initialized."""
        return self._model is not None

    def load(self) -> None:
        """Construct and store the configured Whisper model.

        Raises:
            ImportError: If the optional ``faster-whisper`` dependency is absent.
            RuntimeError: If model construction or model download fails.

        """
        logger.info(
            "Loading Whisper model: %s",
            settings.WHISPER_MODEL_PATH or settings.WHISPER_MODEL_SIZE,
        )
        self._model = _build_model()
        logger.info("Whisper model loaded successfully")

    def get(self) -> _WhisperModel:
        """Return the loaded model or raise when startup has not completed.

        Returns:
            The initialized Whisper model instance.

        Raises:
            RuntimeError: If ``load()`` has not completed successfully.

        """
        if self._model is None:
            raise _WhisperModelNotLoadedError
        return self._model


model_holder = ModelHolder()
