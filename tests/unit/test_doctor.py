# Copyright (c) 2026 Nikolai Zelensky
"""Tests for Whisper, CUDA, and native-tool diagnostics."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from audiodoc import doctor
from audiodoc.config import Settings
from audiodoc.document_engine.diagnostics import NativeToolsStatus
from audiodoc.document_engine.extractors.djvu.tools import DjvuTools
from audiodoc.system_diagnostics import DiagnosticCheck


def _create_model_directory(directory: Path) -> Path:
    directory.mkdir()
    (directory / "config.json").write_text("{}", encoding="utf-8")
    (directory / "model.bin").write_bytes(b"model")
    return directory


def test_whisper_model_check_accepts_configured_local_model(
    tmp_path: Path,
) -> None:
    model_directory = _create_model_directory(tmp_path / "model")
    configured_settings = Settings(WHISPER_MODEL_PATH=str(model_directory))

    result = doctor.check_whisper_model(configured_settings)

    assert result.status == "OK"
    assert "present" in result.message


def test_whisper_model_check_rejects_missing_configured_path(
    tmp_path: Path,
) -> None:
    configured_settings = Settings(WHISPER_MODEL_PATH=str(tmp_path / "missing-model"))

    result = doctor.check_whisper_model(configured_settings)

    assert result.status == "FAIL"
    assert "missing or incomplete" in result.message


def test_whisper_model_check_accepts_cached_model(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    model_directory = _create_model_directory(tmp_path / "cached-model")
    calls: list[tuple[str, bool]] = []

    def fake_download(name: str, *, local_files_only: bool) -> str:
        calls.append((name, local_files_only))
        return str(model_directory)

    monkeypatch.setattr(
        doctor.importlib,
        "import_module",
        lambda _name: SimpleNamespace(download_model=fake_download),
    )

    result = doctor.check_whisper_model(Settings(WHISPER_MODEL_SIZE="small"))

    assert result.status == "OK"
    assert "local cache" in result.message
    assert calls == [("small", True)]


def test_whisper_model_check_accepts_downloadable_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def cache_miss(_name: str, *, local_files_only: bool) -> str:
        assert local_files_only is True
        raise OSError

    monkeypatch.setattr(
        doctor.importlib,
        "import_module",
        lambda _name: SimpleNamespace(download_model=cache_miss),
    )

    result = doctor.check_whisper_model(Settings(WHISPER_MODEL_SIZE="small"))

    assert result.status == "OK"
    assert "downloaded on first startup" in result.message


def test_whisper_model_check_rejects_missing_offline_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def cache_miss(_name: str, *, local_files_only: bool) -> str:
        raise OSError

    monkeypatch.setattr(
        doctor.importlib,
        "import_module",
        lambda _name: SimpleNamespace(download_model=cache_miss),
    )

    result = doctor.check_whisper_model(
        Settings(WHISPER_MODEL_SIZE="small", WHISPER_OFFLINE=True)
    )

    assert result.status == "FAIL"
    assert "WHISPER_OFFLINE" in result.message


def test_whisper_model_check_rejects_unsupported_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def invalid_model(_name: str, *, local_files_only: bool) -> str:
        raise ValueError

    monkeypatch.setattr(
        doctor.importlib,
        "import_module",
        lambda _name: SimpleNamespace(download_model=invalid_model),
    )

    result = doctor.check_whisper_model(Settings(WHISPER_MODEL_SIZE="unknown"))

    assert result.status == "FAIL"
    assert "Unsupported Whisper model" in result.message


def test_whisper_model_check_rejects_missing_dependency(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def missing_dependency(_name: str) -> SimpleNamespace:
        raise ImportError

    monkeypatch.setattr(
        doctor.importlib,
        "import_module",
        missing_dependency,
    )

    result = doctor.check_whisper_model(Settings())

    assert result.status == "FAIL"
    assert "not installed" in result.message


def test_cuda_check_is_not_required_for_cpu() -> None:
    result = doctor.check_cuda_device(Settings(WHISPER_DEVICE="cpu"))

    assert result.status == "OK"
    assert "not required" in result.message


def test_cuda_check_accepts_visible_devices(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        doctor.importlib,
        "import_module",
        lambda _name: SimpleNamespace(get_cuda_device_count=lambda: 2),
    )

    result = doctor.check_cuda_device(Settings(WHISPER_DEVICE="cuda"))

    assert result.status == "OK"
    assert "2 CUDA device(s)" in result.message


def test_cuda_check_rejects_no_visible_devices(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        doctor.importlib,
        "import_module",
        lambda _name: SimpleNamespace(get_cuda_device_count=lambda: 0),
    )

    result = doctor.check_cuda_device(Settings(WHISPER_DEVICE="cuda"))

    assert result.status == "FAIL"
    assert "no CUDA devices" in result.message


def test_cuda_check_rejects_unavailable_ctranslate2(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def missing_dependency(_name: str) -> SimpleNamespace:
        raise ImportError

    monkeypatch.setattr(
        doctor.importlib,
        "import_module",
        missing_dependency,
    )

    result = doctor.check_cuda_device(Settings(WHISPER_DEVICE="cuda"))

    assert result.status == "FAIL"
    assert "ImportError" in result.message


def test_collect_doctor_checks_reports_native_tool_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(doctor, "collect_system_checks", lambda _source: ())
    monkeypatch.setattr(doctor, "load_settings", lambda _source: Settings())
    monkeypatch.setattr(
        doctor,
        "check_whisper_model",
        lambda _settings: DiagnosticCheck("Whisper model", "OK", "Available."),
    )
    monkeypatch.setattr(
        doctor,
        "check_cuda_device",
        lambda _settings: DiagnosticCheck("CUDA", "OK", "Not required."),
    )
    monkeypatch.setattr(
        doctor,
        "check_native_tools",
        lambda: NativeToolsStatus(
            "/usr/bin/tesseract",
            ("eng", "rus"),
            DjvuTools("/usr/bin/djvutxt", "/usr/bin/djvused", "/usr/bin/ddjvu"),
        ),
    )

    checks = doctor.collect_doctor_checks({})

    native_checks = checks[:2]
    assert [check.name for check in native_checks] == ["Tesseract", "DjVuLibre"]
    assert all(check.status == "OK" for check in native_checks)


def test_collect_doctor_checks_reports_missing_native_tools(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(doctor, "collect_system_checks", lambda _source: ())
    monkeypatch.setattr(doctor, "load_settings", lambda _source: Settings())
    monkeypatch.setattr(
        doctor,
        "check_whisper_model",
        lambda _settings: DiagnosticCheck("Whisper model", "OK", "Available."),
    )
    monkeypatch.setattr(
        doctor,
        "check_cuda_device",
        lambda _settings: DiagnosticCheck("CUDA", "OK", "Not required."),
    )
    monkeypatch.setattr(
        doctor,
        "check_native_tools",
        lambda: NativeToolsStatus(
            "/usr/bin/tesseract",
            ("eng",),
            DjvuTools(None, "/usr/bin/djvused", "/usr/bin/ddjvu"),
        ),
    )

    checks = doctor.collect_doctor_checks({})

    assert checks[0].status == "FAIL"
    assert "rus" in checks[0].message
    assert checks[1].status == "FAIL"
    assert "djvutxt" in checks[1].message
