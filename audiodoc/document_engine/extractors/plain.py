# Copyright (c) 2026 Nikolai Zelensky
"""Extract plain text and Markdown while applying the shared output budget."""

from audiodoc.document_engine.extractors.base import ExtractContext, make_context


def extract_plain(
    data: bytes,
    *,
    context: ExtractContext | None = None,
) -> str:
    """Decode TXT/Markdown as UTF-8 and return only the remaining text budget."""
    ctx = make_context(context)
    ctx.check()
    return ctx.budget.add(data.decode("utf-8-sig", errors="replace"))
