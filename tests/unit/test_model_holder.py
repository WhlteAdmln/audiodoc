from types import SimpleNamespace

import pytest

import backend.transcription.model as model_module
from backend.transcription.model import ModelHolder


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
