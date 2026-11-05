"""Whisper runtime and offline mode are read from application settings."""

import sys
from types import ModuleType

import backend.transcription.model as model_module
from backend.config import settings


def test_whisper_model_factory_uses_configurable_device_and_offline_options(
    monkeypatch,
):
    captured = {}

    def fake_whisper_model(model_path, **kwargs):
        captured["model_path"] = model_path
        captured.update(kwargs)
        return object()

    fake_module = ModuleType("faster_whisper")
    fake_module.WhisperModel = fake_whisper_model
    monkeypatch.setitem(sys.modules, "faster_whisper", fake_module)
    monkeypatch.setattr(settings, "WHISPER_MODEL_SIZE", "small")
    monkeypatch.setattr(settings, "WHISPER_MODEL_PATH", "/opt/models/whisper-small")
    monkeypatch.setattr(settings, "WHISPER_DEVICE", "cuda")
    monkeypatch.setattr(settings, "WHISPER_COMPUTE_TYPE", "float16")
    monkeypatch.setattr(settings, "WHISPER_CPU_THREADS", 6)
    monkeypatch.setattr(settings, "WHISPER_OFFLINE", True)

    model_module._build_model()

    assert captured == {
        "model_path": "/opt/models/whisper-small",
        "device": "cuda",
        "compute_type": "float16",
        "cpu_threads": 6,
        "local_files_only": True,
    }
