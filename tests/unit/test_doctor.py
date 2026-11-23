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

    expected_status = "OK"
    assert result.status == expected_status
    expected_fragment = "present"
    assert expected_fragment in result.message


def test_whisper_model_check_rejects_missing_configured_path(
    tmp_path: Path,
) -> None:
    configured_settings = Settings(WHISPER_MODEL_PATH=str(tmp_path / "missing-model"))

    result = doctor.check_whisper_model(configured_settings)

    expected_status = "FAIL"
    assert result.status == expected_status
    expected_fragment = "missing or incomplete"
    assert expected_fragment in result.message


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

    expected_status = "OK"
    assert result.status == expected_status
    expected_fragment = "local cache"
    assert expected_fragment in result.message
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

    expected_status = "OK"
    assert result.status == expected_status
    expected_fragment = "downloaded on first startup"
    assert expected_fragment in result.message


def test_whisper_model_check_rejects_missing_offline_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def cache_miss(_name: str, **_kwargs: object) -> str:
        raise OSError

    monkeypatch.setattr(
        doctor.importlib,
        "import_module",
        lambda _name: SimpleNamespace(download_model=cache_miss),
    )

    result = doctor.check_whisper_model(
        Settings(WHISPER_MODEL_SIZE="small", WHISPER_OFFLINE=True)
    )

    expected_status = "FAIL"
    assert result.status == expected_status
    expected_fragment = "WHISPER_OFFLINE"
    assert expected_fragment in result.message


def test_whisper_model_check_requires_cached_model_when_forced_offline(
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

    result = doctor.check_whisper_model(
        Settings(WHISPER_MODEL_SIZE="small", WHISPER_OFFLINE=False),
        offline=True,
    )

    expected_status = "FAIL"
    assert result.status == expected_status
    expected_fragment = "local cache"
    assert expected_fragment in result.message
    expected_fragment = "offline mode"
    assert expected_fragment in result.message


def test_whisper_model_check_rejects_unsupported_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def invalid_model(_name: str, **_kwargs: object) -> str:
        raise ValueError

    monkeypatch.setattr(
        doctor.importlib,
        "import_module",
        lambda _name: SimpleNamespace(download_model=invalid_model),
    )

    result = doctor.check_whisper_model(Settings(WHISPER_MODEL_SIZE="unknown"))

    expected_status = "FAIL"
    assert result.status == expected_status
    expected_fragment = "Unsupported Whisper model"
    assert expected_fragment in result.message


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

    expected_status = "FAIL"
    assert result.status == expected_status
    expected_fragment = "not installed"
    assert expected_fragment in result.message


def test_cuda_check_is_not_required_for_cpu() -> None:
    result = doctor.check_cuda_device(Settings(WHISPER_DEVICE="cpu"))

    expected_status = "OK"
    assert result.status == expected_status
    expected_fragment = "not required"
    assert expected_fragment in result.message


def test_cuda_check_accepts_visible_devices(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        doctor.importlib,
        "import_module",
        lambda _name: SimpleNamespace(get_cuda_device_count=lambda: 2),
    )

    result = doctor.check_cuda_device(Settings(WHISPER_DEVICE="cuda"))

    expected_status = "OK"
    assert result.status == expected_status
    expected_fragment = "2 CUDA device(s)"
    assert expected_fragment in result.message


def test_cuda_check_rejects_no_visible_devices(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        doctor.importlib,
        "import_module",
        lambda _name: SimpleNamespace(get_cuda_device_count=lambda: 0),
    )

    result = doctor.check_cuda_device(Settings(WHISPER_DEVICE="cuda"))

    expected_status = "FAIL"
    assert result.status == expected_status
    expected_fragment = "no CUDA devices"
    assert expected_fragment in result.message


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

    expected_status = "FAIL"
    assert result.status == expected_status
    expected_fragment = "ImportError"
    assert expected_fragment in result.message


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
    expected_status = "OK"
    assert all(check.status == expected_status for check in native_checks)


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

    expected_status = "FAIL"
    assert checks[0].status == expected_status
    expected_fragment = "rus"
    assert expected_fragment in checks[0].message
    expected_status = "FAIL"
    assert checks[1].status == expected_status
    expected_fragment = "djvutxt"
    assert expected_fragment in checks[1].message
