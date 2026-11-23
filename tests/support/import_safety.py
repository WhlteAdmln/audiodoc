# Copyright (c) 2026 Nikolai Zelensky
"""Child-process check that importing audiodoc.main has no side effects.

The check runs in a spawned process that imports this module to find its target, so
it must not import audiodoc.main itself or through other test modules.
"""

import builtins
import importlib
import io
import logging
import os
import sys
from collections.abc import Callable
from typing import Any

_MAIN_MODULE = "audiodoc.main"
_IMPORT_DEPENDENCIES = (
    "fastapi",
    "audiodoc.api",
    "audiodoc.api.auth",
    "audiodoc.api.error_handlers",
    "audiodoc.api.middleware",
    "audiodoc.common.request_id",
    "audiodoc.config",
    "audiodoc.document_engine",
    "audiodoc.document_engine.limits",
    "audiodoc.logging_setup",
    "audiodoc.transcription.model",
    "audiodoc.transcription.temp_files",
)


def _track_open(
    original: Callable[..., Any],
    opened_paths: list[str],
) -> Callable[..., Any]:
    def tracked(file: object, *args: object, **kwargs: object) -> object:
        opened_paths.append(str(file))
        return original(file, *args, **kwargs)

    return tracked


def check_import_safety(working_directory: str) -> None:
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

    assert _MAIN_MODULE not in sys.modules
    importlib.import_module(_MAIN_MODULE)

    assert tuple(root_logger.handlers) == handlers_before
    assert not opened_paths, opened_paths
