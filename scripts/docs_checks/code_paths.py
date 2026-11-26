# Copyright (c) 2026 Nikolai Zelensky
"""Check that repository paths named in inline code exist."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from scripts.docs_checks.markdown import FENCED_BLOCK_RE, display_path

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

_DOCUMENT_PATTERNS = ("README*.md", "CONTRIBUTING*.md", "docs/**/*.md")
_PATH_PREFIXES = ("audiodoc/", "scripts/", "tests/")
_PLACEHOLDER_RE = re.compile(r"<[^<>]+>")
_INLINE_CODE_RE = re.compile(r"`([^`\n]+)`")


def _documents(root: Path) -> list[Path]:
    """Return the documents whose inline code paths are checked."""
    return sorted(
        {path for pattern in _DOCUMENT_PATTERNS for path in root.glob(pattern)}
    )


def _repository_path(segment: str) -> str | None:
    """Return the repository path an inline code segment names, if any."""
    words = segment.split()
    if not words or not words[0].startswith(_PATH_PREFIXES):
        return None
    if _PLACEHOLDER_RE.search(segment) is not None:
        return None
    return words[0].split("::", 1)[0]


def _inline_paths(text: str) -> Iterator[tuple[int, str]]:
    """Yield the line number and path of each inline code path outside fences."""
    text = FENCED_BLOCK_RE.sub(lambda match: "\n" * match.group(0).count("\n"), text)
    for line_number, line in enumerate(text.splitlines(), start=1):
        for segment in _INLINE_CODE_RE.findall(line):
            path = _repository_path(segment)
            if path is not None:
                yield line_number, path


def check_code_paths(root: Path) -> list[str]:
    """Check that the repository paths named in inline code exist."""
    errors: list[str] = []

    for document in _documents(root):
        text = document.read_text(encoding="utf-8")
        for line_number, path in _inline_paths(text):
            if not (root / path).exists():
                errors.append(
                    f"{display_path(document, root)}:{line_number}: "
                    f"missing path '{path}'"
                )

    return errors
