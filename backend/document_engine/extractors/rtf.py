# Copyright (c) 2026 Nikolai Zelensky
"""Extract readable text from Rich Text Format documents."""

from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from collections.abc import Callable

from striprtf.striprtf import rtf_to_text

from backend.document_engine.extractors.base import ExtractContext, make_context


def extract_rtf(data: bytes, *, context: ExtractContext | None = None) -> str:
    """Convert RTF to plain text and apply the remaining output budget."""
    ctx = make_context(context)
    ctx.check()
    convert = cast("Callable[[str], str]", rtf_to_text)
    text = convert(data.decode("utf-8", errors="replace"))
    ctx.check()
    return ctx.budget.add(text)
