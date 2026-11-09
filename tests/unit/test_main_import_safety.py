# Copyright (c) 2026 Nikolai Zelensky
"""Ensure importing backend.main does not configure logging or open files."""

import builtins
import importlib
import io
import logging
import multiprocessing
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

_IMPORT_DEPENDENCIES = (
    "fastapi",
    "backend.api",
    "backend.api.auth",
    "backend.api.error_handlers",
    "backend.api.middleware",
    "backend.common.logging_setup",
    "backend.common.request_id",
    "backend.config",
    "backend.document_engine",
    "backend.document_engine.limits",
    "backend.transcription.model",
    "backend.transcription.temp_files",
)


def _track_open(
    original: Callable[..., Any],
    opened_paths: list[str],
) -> Callable[..., Any]:
    def tracked(file: object, *args: Any, **kwargs: Any) -> Any:
        opened_paths.append(str(file))
        return original(file, *args, **kwargs)

    return tracked


def _check_import_safety(working_directory: str) -> None:
    """Check import side effects in a clean child process."""
    os.chdir(working_directory)

    for module_name in _IMPORT_DEPENDENCIES:
        importlib.import_module(module_name)

    opened_paths: list[str] = []
    builtins.open = _track_open(builtins.open, opened_paths)
    io.open = _track_open(io.open, opened_paths)
    os.open = _track_open(os.open, opened_paths)

    root_logger = logging.getLogger()
    handlers_before = tuple(root_logger.handlers)

    assert "backend.main" not in __import__("sys").modules
    importlib.import_module("backend.main")

    assert tuple(root_logger.handlers) == handlers_before
    assert opened_paths == [], opened_paths


def test_import_backend_main_has_no_side_effects(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root = Path(__file__).resolve().parents[2]
    path = os.environ.get("PATH", os.defpath)

    for name in tuple(os.environ):
        monkeypatch.delenv(name, raising=False)

    clean_environment = {
        "HOME": str(tmp_path),
        "PATH": path,
        "PYTHONPATH": str(project_root),
        "PYTHONNOUSERSITE": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "TMPDIR": str(tmp_path),
    }
    for name, value in clean_environment.items():
        monkeypatch.setenv(name, value)

    context = multiprocessing.get_context("spawn")
    process = context.Process(
        target=_check_import_safety,
        args=(str(tmp_path),),
    )

    process.start()
    process.join(timeout=30)

    if process.is_alive():
        process.terminate()
        process.join()
        pytest.fail("Import safety child process timed out")

    assert process.exitcode == 0
