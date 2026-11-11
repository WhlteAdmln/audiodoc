# Copyright (c) 2026 Nikolai Zelensky
"""Installation diagnostics for Whisper, CUDA, and native tools."""

import importlib
import os
from collections.abc import Mapping
from pathlib import Path

from audiodoc.config import ConfigError, Settings, load_settings
from audiodoc.document_engine.diagnostics import check_native_tools
from audiodoc.system_diagnostics import DiagnosticCheck, collect_system_checks

REQUIRED_TESSERACT_LANGUAGES = ("rus", "eng")


def _model_files_present(directory: Path) -> bool:
    """Return whether a directory contains the essential Whisper model files."""
    return (
        directory.is_dir()
        and (directory / "config.json").is_file()
        and (directory / "model.bin").is_file()
    )


def _check_configured_model(model_directory: Path) -> DiagnosticCheck:
    """Check a model stored at an explicitly configured path."""
    if _model_files_present(model_directory):
        return DiagnosticCheck(
            "Whisper model",
            "OK",
            f"Model files are present: {model_directory}.",
        )
    return DiagnosticCheck(
        "Whisper model",
        "FAIL",
        f"Configured model directory is missing or incomplete: {model_directory}.",
    )


def _check_model_cache(model_name: str, offline: bool) -> DiagnosticCheck:
    """Check whether a named model is cached or can be downloaded."""
    try:
        download_model = importlib.import_module("faster_whisper.utils").download_model
    except ImportError:
        return DiagnosticCheck(
            "Whisper model",
            "FAIL",
            "faster-whisper is not installed.",
        )

    cached_path: Path | None = None
    try:
        cached_path = Path(download_model(model_name, local_files_only=True))
    except ValueError:
        return DiagnosticCheck(
            "Whisper model",
            "FAIL",
            f"Unsupported Whisper model name: {model_name}.",
        )
    except OSError:
        pass

    if cached_path is not None and _model_files_present(cached_path):
        return DiagnosticCheck(
            "Whisper model",
            "OK",
            f"Model {model_name!r} is available in the local cache.",
        )

    if offline:
        return DiagnosticCheck(
            "Whisper model",
            "FAIL",
            f"Model {model_name!r} is not available or is incomplete "
            "in the local cache while WHISPER_OFFLINE is enabled.",
        )

    return DiagnosticCheck(
        "Whisper model",
        "OK",
        f"Model {model_name!r} is not cached locally; it can be "
        "downloaded on first startup.",
    )


def check_whisper_model(configured_settings: Settings) -> DiagnosticCheck:
    """Check whether the configured Whisper model is present or downloadable."""
    configured_path = configured_settings.WHISPER_MODEL_PATH
    if configured_path:
        return _check_configured_model(Path(configured_path))

    return _check_model_cache(
        configured_settings.WHISPER_MODEL_SIZE,
        configured_settings.WHISPER_OFFLINE,
    )


def check_cuda_device(configured_settings: Settings) -> DiagnosticCheck:
    """Check CUDA visibility when the configured Whisper device requires it."""
    if configured_settings.WHISPER_DEVICE != "cuda":
        return DiagnosticCheck(
            "CUDA",
            "OK",
            f"CUDA is not required for WHISPER_DEVICE="
            f"{configured_settings.WHISPER_DEVICE!r}.",
        )

    try:
        ctranslate2 = importlib.import_module("ctranslate2")
        device_count = int(ctranslate2.get_cuda_device_count())
    except (
        AttributeError,
        ImportError,
        OSError,
        RuntimeError,
        TypeError,
        ValueError,
    ) as error:
        return DiagnosticCheck(
            "CUDA",
            "FAIL",
            f"Unable to inspect CUDA devices: {type(error).__name__}.",
        )

    if device_count < 1:
        return DiagnosticCheck(
            "CUDA",
            "FAIL",
            "WHISPER_DEVICE=cuda but no CUDA devices are visible to CTranslate2.",
        )

    return DiagnosticCheck(
        "CUDA",
        "OK",
        f"CTranslate2 can see {device_count} CUDA device(s).",
    )


def _collect_native_checks() -> tuple[DiagnosticCheck, ...]:
    """Convert shared native-tool information into diagnostic results."""
    native_tools = check_native_tools()
    checks: list[DiagnosticCheck] = []

    if native_tools.tesseract is None:
        checks.append(
            DiagnosticCheck(
                "Tesseract",
                "FAIL",
                "The Tesseract executable was not found.",
            )
        )
    else:
        missing_languages = [
            language
            for language in REQUIRED_TESSERACT_LANGUAGES
            if language not in native_tools.languages
        ]
        if missing_languages:
            checks.append(
                DiagnosticCheck(
                    "Tesseract",
                    "FAIL",
                    "Missing language data: " + ", ".join(missing_languages) + ".",
                )
            )
        else:
            checks.append(
                DiagnosticCheck(
                    "Tesseract",
                    "OK",
                    f"Executable found at {native_tools.tesseract}; "
                    "rus and eng languages are available.",
                )
            )

    missing_djvu_tools = [
        name
        for name, path in (
            ("djvutxt", native_tools.djvu_tools.djvutxt),
            ("djvused", native_tools.djvu_tools.djvused),
            ("ddjvu", native_tools.djvu_tools.ddjvu),
        )
        if path is None
    ]

    if missing_djvu_tools:
        checks.append(
            DiagnosticCheck(
                "DjVuLibre",
                "FAIL",
                "Missing executables: " + ", ".join(missing_djvu_tools) + ".",
            )
        )
    else:
        checks.append(
            DiagnosticCheck(
                "DjVuLibre",
                "OK",
                "All required DjVuLibre executables are available.",
            )
        )

    return tuple(checks)


def collect_doctor_checks(
    environ: Mapping[str, str] | None = None,
) -> tuple[DiagnosticCheck, ...]:
    """Collect system, native dependency, model, and CUDA diagnostics."""
    source = os.environ if environ is None else environ
    checks = [*collect_system_checks(source), *_collect_native_checks()]

    try:
        configured_settings = load_settings(source)
    except ConfigError as error:
        problems = "; ".join(problem.partition(" Got:")[0] for problem in error.errors)
        checks.append(
            DiagnosticCheck(
                "Whisper configuration",
                "FAIL",
                f"Invalid application settings: {problems}.",
            )
        )
    else:
        checks.append(check_whisper_model(configured_settings))
        checks.append(check_cuda_device(configured_settings))

    return tuple(checks)
