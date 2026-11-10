# Copyright (c) 2026 Nikolai Zelensky
from types import SimpleNamespace

import pytest

import audiodoc.transcription.model as model_module
from audiodoc.config import Settings
from audiodoc.transcription.model import ModelHolder


def test_model_holder_reports_not_loaded_and_raises_from_get():
    holder = ModelHolder()
    assert holder.is_loaded is False
    with pytest.raises(RuntimeError, match="Whisper model is not loaded"):
        holder.get()


def test_model_holder_loads_once_from_factory(monkeypatch):
    created = SimpleNamespace(name="fake-whisper")
    calls = []

    def build_model():
        calls.append(True)
        return created

    monkeypatch.setattr(model_module, "_build_model", build_model)
    holder = ModelHolder()

    holder.load()

    assert holder.is_loaded is True
    assert holder.get() is created
    assert calls == [True]


def test_model_holder_passes_application_settings_to_factory(monkeypatch):
    configured_settings = Settings(
        WHISPER_MODEL_SIZE="large",
        WHISPER_DEVICE="cuda",
    )
    created = SimpleNamespace(name="application-whisper")
    received_settings: list[Settings] = []

    def build_model(settings: Settings) -> SimpleNamespace:
        received_settings.append(settings)
        return created

    monkeypatch.setattr(model_module, "_build_model", build_model)
    holder = ModelHolder(configured_settings)

    holder.load()

    assert holder.get() is created
    assert received_settings == [configured_settings]


def test_build_model_uses_supplied_application_settings(monkeypatch):
    configured_settings = Settings(
        WHISPER_MODEL_SIZE="small",
        WHISPER_MODEL_PATH="/models/custom",
        WHISPER_DEVICE="cuda",
        WHISPER_COMPUTE_TYPE="float16",
        WHISPER_CPU_THREADS=3,
        WHISPER_OFFLINE=True,
    )
    captured: dict[str, object] = {}

    def fake_whisper_model(model_path: str, **kwargs: object) -> SimpleNamespace:
        captured["model_path"] = model_path
        captured.update(kwargs)
        return SimpleNamespace(name="fake")

    fake_module = SimpleNamespace(WhisperModel=fake_whisper_model)
    monkeypatch.setattr(
        model_module.importlib,
        "import_module",
        lambda _name: fake_module,
    )

    model_module._build_model(configured_settings)

    assert captured == {
        "model_path": "/models/custom",
        "device": "cuda",
        "compute_type": "float16",
        "cpu_threads": 3,
        "local_files_only": True,
    }
