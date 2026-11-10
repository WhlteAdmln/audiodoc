# Copyright (c) 2026 Nikolai Zelensky
"""Locate external DjVuLibre tools."""

import shutil
from dataclasses import dataclass

from backend.errors.documents import DependencyMissingError


@dataclass(frozen=True)
class DjvuTools:
    """Paths to DjVuLibre executables."""

    djvutxt: str | None
    djvused: str | None
    ddjvu: str | None


def find_djvu_tools() -> DjvuTools:
    """Find djvutxt, djvused, and ddjvu on PATH."""
    return DjvuTools(
        djvutxt=shutil.which("djvutxt"),
        djvused=shutil.which("djvused"),
        ddjvu=shutil.which("ddjvu"),
    )


def require_djvutxt(tools: DjvuTools) -> str:
    """Require the DjVu text-layer reader."""
    if tools.djvutxt is None:
        raise DependencyMissingError
    return tools.djvutxt
