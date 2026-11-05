"""Lifecycle holder for the process-wide Whisper model."""

import logging
from typing import Any

from backend.config import settings

logger = logging.getLogger(__name__)


def _build_model() -> Any:
    """Construct Whisper lazily so API modules remain importable without the extra."""
    from faster_whisper import WhisperModel

    model_path = settings.WHISPER_MODEL_PATH or settings.WHISPER_MODEL_SIZE
    return WhisperModel(
        model_path,
        device=settings.WHISPER_DEVICE,
        compute_type=settings.WHISPER_COMPUTE_TYPE,
        cpu_threads=settings.WHISPER_CPU_THREADS,
        local_files_only=settings.WHISPER_OFFLINE,
    )


class ModelHolder:
    """Owns the single Whisper model instance for this application process."""

    def __init__(self) -> None:
        self._model: Any | None = None

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

    def get(self) -> Any:
        """Return the loaded model or raise when startup has not completed.

        Returns:
            The initialized Whisper model instance.

        Raises:
            RuntimeError: If ``load()`` has not completed successfully.
        """
        if self._model is None:
            raise RuntimeError("Whisper model is not loaded")
        return self._model


model_holder = ModelHolder()
