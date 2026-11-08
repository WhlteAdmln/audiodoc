# Copyright (c) 2026 Nikolai Zelensky
"""Extract ODT headings and paragraphs within the shared character budget."""

from odf import teletype
from odf.text import H, P

from backend.document_engine.extractors.base import (
    ExtractContext,
    add_chunk,
    make_context,
    odf_elements,
)


def extract_odt(document: object, *, context: ExtractContext | None = None) -> str:
    """Extract ODT headings and paragraphs, stopping as soon as the budget fills."""
    ctx = make_context(context)
    result: list[str] = []

    for element_type in (H, P):
        for element in odf_elements(document, element_type):
            ctx.check()
            text = teletype.extractText(element).strip()
            if text:
                add_chunk(result, ctx, text)
            if ctx.budget.is_truncated():
                return "\n".join(result)
    ctx.check()
    return "\n".join(result)
