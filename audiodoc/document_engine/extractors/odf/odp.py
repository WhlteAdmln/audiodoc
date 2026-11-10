# Copyright (c) 2026 Nikolai Zelensky
"""Extract OpenDocument Presentation slide text within the shared text budget."""

from odf import teletype
from odf.draw import Page
from odf.text import H, P

from audiodoc.document_engine.extractors.base import (
    ExtractContext,
    add_chunk,
    make_context,
    odf_elements,
)
from audiodoc.errors.messages import EXTRACTION_MESSAGES


def extract_odp(document: object, *, context: ExtractContext | None = None) -> str:
    """Extract ODP text until additional content exceeds the shared budget."""
    ctx = make_context(context)
    result: list[str] = []

    for index, page in enumerate(odf_elements(document, Page)):
        ctx.check()
        add_chunk(
            result,
            ctx,
            EXTRACTION_MESSAGES["odf_slide_label"].format(index=index + 1),
        )
        if ctx.budget.is_truncated():
            break

        for element_type in (P, H):
            for paragraph in odf_elements(page, element_type):
                ctx.check()
                text = teletype.extractText(paragraph).strip()
                if text:
                    add_chunk(result, ctx, text)
                if ctx.budget.is_truncated():
                    break
            if ctx.budget.is_truncated():
                break
        if ctx.budget.is_truncated():
            break

    ctx.check()
    return "\n".join(result)
