# Copyright (c) 2026 Nikolai Zelensky

"""Fake Whisper models for transcription tests."""

import contextlib
import threading
from types import SimpleNamespace

import pytest

from audiodoc.transcription import model as model_module
from audiodoc.transcription.model import ModelHolder


class FakeWhisperModel:
    """Return one recognized segment and remember the calling thread."""

    def __init__(self, duration: float = 1.5) -> None:
        """Store the reported audio duration."""
        self.duration = duration
        self.thread_id: int | None = None

    def transcribe(self, _path: object, **_kwargs: object) -> object:
        """Record the worker thread and return one segment."""
        self.thread_id = threading.get_ident()
        segments = [SimpleNamespace(text=" recognized text ")]
        return iter(segments), SimpleNamespace(language="ru", duration=self.duration)


def silent_model() -> SimpleNamespace:
    """Make a model that recognizes nothing and reports no audio info."""

    def transcribe(*_args: object, **_kwargs: object) -> object:
        return iter([]), None

    return SimpleNamespace(transcribe=transcribe)


def loaded_model_holder(model: object) -> ModelHolder:
    """Load a model holder whose model builder returns the given model."""
    holder = ModelHolder()
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(model_module, "_build_model", lambda *_args: model)
        holder.load()
    return holder


class ModelBuildError(RuntimeError):
    """Raised by a model builder that cannot create the model."""


def _fail_build(*_args: object) -> object:
    raise ModelBuildError


def failed_model_holder() -> ModelHolder:
    """Return a model holder whose model failed to load."""
    holder = ModelHolder()
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(model_module, "_build_model", _fail_build)
        with contextlib.suppress(ModelBuildError):
            holder.load()
    return holder


class UnexpectedSegmentIterationError(AssertionError):
    """Raised when a test consumes the segments of overlong audio."""

    def __init__(self) -> None:
        """Explain which contract the code under test broke."""
        super().__init__("segments should not be consumed for overlong audio")


def speech_model() -> SimpleNamespace:
    """Make a model that recognizes one phrase in any non-empty audio."""

    def transcribe(audio: object, **_kwargs: object) -> object:
        assert getattr(audio, "size", 0) > 0
        segments = [SimpleNamespace(text=" recognized speech ")]
        return iter(segments), SimpleNamespace(language="ru", duration=1.5)

    return SimpleNamespace(transcribe=transcribe)


def overlong_model() -> SimpleNamespace:
    """Make a model that reports overlong audio and must not be iterated."""

    def transcribe(_audio: object, **_kwargs: object) -> object:
        def segments() -> object:
            raise UnexpectedSegmentIterationError
            yield None

        return segments(), SimpleNamespace(language="ru", duration=9999)

    return SimpleNamespace(transcribe=transcribe)


def no_native_tools() -> SimpleNamespace:
    """Report that no OCR or DjVu tools are installed."""
    return SimpleNamespace(tesseract=None, languages=(), djvulibre=False)
