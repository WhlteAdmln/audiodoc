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


def _patch_doctor_checks(
    monkeypatch: pytest.MonkeyPatch,
    native_tools: NativeToolsStatus,
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
    monkeypatch.setattr(doctor, "check_native_tools", lambda: native_tools)


@pytest.fixture(name="cached_model_calls")
def fixture_cached_model_calls(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> list[tuple[str, bool]]:
    """Serve a cached Whisper model and record each download request."""
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
    return calls


@pytest.fixture(name="cache_miss_calls")
def fixture_cache_miss_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> list[tuple[str, bool]]:
    """Miss the Whisper model cache and record each download request."""
    calls: list[tuple[str, bool]] = []

    def cache_miss(name: str, *, local_files_only: bool) -> str:
        calls.append((name, local_files_only))
        raise OSError

    monkeypatch.setattr(
        doctor.importlib,
        "import_module",
        lambda _name: SimpleNamespace(download_model=cache_miss),
    )
    return calls


@pytest.fixture(name="missing_native_tools_checks")
def fixture_missing_native_tools_checks(
    monkeypatch: pytest.MonkeyPatch,
) -> list[DiagnosticCheck]:
    """Collect doctor checks with a missing OCR language and DjVu tool."""
    _patch_doctor_checks(
        monkeypatch,
        NativeToolsStatus(
            "/usr/bin/tesseract",
            ("eng",),
            DjvuTools(None, "/usr/bin/djvused", "/usr/bin/ddjvu"),
        ),
    )
    return list(doctor.collect_doctor_checks({}))


def test_whisper_model_check_accepts_configured_local_model(
    tmp_path: Path,
) -> None:
    model_directory = _create_model_directory(tmp_path / "model")
    configured_settings = Settings(WHISPER_MODEL_PATH=str(model_directory))

    result = doctor.check_whisper_model(configured_settings)

    present_detail = "present"
    expected = ("OK", True)
    assert (result.status, present_detail in result.message) == expected, (
        f"configured local model was not accepted: {result}"
    )


def test_whisper_model_check_rejects_missing_configured_path(
    tmp_path: Path,
) -> None:
    configured_settings = Settings(WHISPER_MODEL_PATH=str(tmp_path / "missing-model"))

    result = doctor.check_whisper_model(configured_settings)

    missing_detail = "missing or incomplete"
    expected = ("FAIL", True)
    assert (result.status, missing_detail in result.message) == expected, (
        f"missing configured model path was not rejected: {result}"
    )


def test_whisper_model_check_accepts_cached_model(
    cached_model_calls: list[tuple[str, bool]],
) -> None:
    result = doctor.check_whisper_model(Settings(WHISPER_MODEL_SIZE="small"))

    cache_detail = "local cache"
    expected = ("OK", True)
    assert (result.status, cache_detail in result.message) == expected, (
        f"cached model was not accepted: {result}, calls {cached_model_calls}"
    )


def test_whisper_model_check_looks_up_cached_model_locally(
    cached_model_calls: list[tuple[str, bool]],
) -> None:
    doctor.check_whisper_model(Settings(WHISPER_MODEL_SIZE="small"))

    expected_calls = [("small", True)]
    assert cached_model_calls == expected_calls, (
        "cached model was not looked up once in the local cache only"
    )


def test_whisper_model_check_accepts_downloadable_model(
    cache_miss_calls: list[tuple[str, bool]],
) -> None:
    result = doctor.check_whisper_model(Settings(WHISPER_MODEL_SIZE="medium.en"))

    download_detail = "downloaded on first startup"
    expected = ("OK", True)
    assert (result.status, download_detail in result.message) == expected, (
        f"downloadable model was not accepted: {result}, calls {cache_miss_calls}"
    )


def test_whisper_model_check_probes_only_local_cache_for_downloadable_model(
    cache_miss_calls: list[tuple[str, bool]],
) -> None:
    doctor.check_whisper_model(Settings(WHISPER_MODEL_SIZE="base"))

    expected_calls = [("base", True)]
    assert cache_miss_calls == expected_calls, (
        "downloadable model check did not probe only the local cache"
    )


def test_whisper_model_check_rejects_missing_offline_model(
    cache_miss_calls: list[tuple[str, bool]],
) -> None:
    result = doctor.check_whisper_model(
        Settings(WHISPER_MODEL_SIZE="small", WHISPER_OFFLINE=True)
    )

    offline_setting = "WHISPER_OFFLINE"
    expected = ("FAIL", True)
    assert (result.status, offline_setting in result.message) == expected, (
        f"missing offline model was not rejected: {result}, calls {cache_miss_calls}"
    )


def test_whisper_model_check_requires_cached_model_when_forced_offline(
    cache_miss_calls: list[tuple[str, bool]],
) -> None:
    result = doctor.check_whisper_model(
        Settings(WHISPER_MODEL_SIZE="small", WHISPER_OFFLINE=False),
        offline=True,
    )

    cache_detail = "local cache"
    offline_detail = "offline mode"
    expected = ("FAIL", True, True)
    actual = (
        result.status,
        cache_detail in result.message,
        offline_detail in result.message,
    )
    assert actual == expected, (
        f"forced offline mode accepted an uncached model: {result}, "
        f"calls {cache_miss_calls}"
    )


def test_whisper_model_check_probes_only_local_cache_when_forced_offline(
    cache_miss_calls: list[tuple[str, bool]],
) -> None:
    doctor.check_whisper_model(
        Settings(WHISPER_MODEL_SIZE="large-v3", WHISPER_OFFLINE=False),
        offline=True,
    )

    expected_calls = [("large-v3", True)]
    assert cache_miss_calls == expected_calls, (
        "forced offline check did not probe only the local cache"
    )


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

    unsupported_detail = "Unsupported Whisper model"
    expected = ("FAIL", True)
    assert (result.status, unsupported_detail in result.message) == expected, (
        f"unsupported model was not rejected: {result}"
    )


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

    missing_dependency_detail = "not installed"
    expected = ("FAIL", True)
    assert (result.status, missing_dependency_detail in result.message) == expected, (
        f"missing faster-whisper dependency was not rejected: {result}"
    )


def test_cuda_check_is_not_required_for_cpu() -> None:
    result = doctor.check_cuda_device(Settings(WHISPER_DEVICE="cpu"))

    not_required_detail = "not required"
    expected = ("OK", True)
    assert (result.status, not_required_detail in result.message) == expected, (
        f"CUDA was required for the CPU device: {result}"
    )


def test_cuda_check_accepts_visible_devices(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        doctor.importlib,
        "import_module",
        lambda _name: SimpleNamespace(get_cuda_device_count=lambda: 2),
    )

    result = doctor.check_cuda_device(Settings(WHISPER_DEVICE="cuda"))

    device_count_detail = "2 CUDA device(s)"
    expected = ("OK", True)
    assert (result.status, device_count_detail in result.message) == expected, (
        f"visible CUDA devices were not accepted: {result}"
    )


def test_cuda_check_rejects_no_visible_devices(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        doctor.importlib,
        "import_module",
        lambda _name: SimpleNamespace(get_cuda_device_count=lambda: 0),
    )

    result = doctor.check_cuda_device(Settings(WHISPER_DEVICE="cuda"))

    no_device_detail = "no CUDA devices"
    expected = ("FAIL", True)
    assert (result.status, no_device_detail in result.message) == expected, (
        f"missing CUDA devices were not rejected: {result}"
    )


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

    import_error_detail = "ImportError"
    expected = ("FAIL", True)
    assert (result.status, import_error_detail in result.message) == expected, (
        f"unavailable ctranslate2 was not rejected: {result}"
    )


def test_collect_doctor_checks_reports_native_tool_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_doctor_checks(
        monkeypatch,
        NativeToolsStatus(
            "/usr/bin/tesseract",
            ("eng", "rus"),
            DjvuTools("/usr/bin/djvutxt", "/usr/bin/djvused", "/usr/bin/ddjvu"),
        ),
    )

    checks = doctor.collect_doctor_checks({})

    actual = [(check.name, check.status) for check in checks[:2]]
    expected = [("Tesseract", "OK"), ("DjVuLibre", "OK")]
    assert actual == expected, "native tool checks did not report success first"


def test_collect_doctor_checks_reports_missing_tesseract_language(
    missing_native_tools_checks: list[DiagnosticCheck],
) -> None:
    tesseract_check = missing_native_tools_checks[0]

    missing_language = "rus"
    expected = ("FAIL", True)
    actual = (tesseract_check.status, missing_language in tesseract_check.message)
    assert actual == expected, (
        f"missing Tesseract language was not reported: {tesseract_check}"
    )


def test_collect_doctor_checks_reports_missing_djvu_tool(
    missing_native_tools_checks: list[DiagnosticCheck],
) -> None:
    djvu_check = missing_native_tools_checks[1]

    missing_tool = "djvutxt"
    expected = ("FAIL", True)
    actual = (djvu_check.status, missing_tool in djvu_check.message)
    assert actual == expected, f"missing DjVuLibre tool was not reported: {djvu_check}"
