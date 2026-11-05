"""Extract OpenDocument Presentation slide text within the shared text budget."""

from odf import teletype
from odf.draw import Page
from odf.text import H, P

from backend.document_engine.extractors.base import (
    ExtractContext,
    add_chunk,
    make_context,
)


def extract_odp(document: object, *, context: ExtractContext | None = None) -> str:
    """Extract ODP slide headings and paragraphs until the budget is exhausted."""
    ctx = make_context(context)
    result: list[str] = []

    for index, page in enumerate(document.getElementsByType(Page)):
        ctx.check()
        add_chunk(result, ctx, f"--- Слайд {index + 1} ---")
        if ctx.budget.exhausted:
            break

        for element_type in (P, H):
            for paragraph in page.getElementsByType(element_type):
                ctx.check()
                text = teletype.extractText(paragraph).strip()
                if text:
                    add_chunk(result, ctx, text)
                if ctx.budget.exhausted:
                    break
            if ctx.budget.exhausted:
                break
        if ctx.budget.exhausted:
            break

    ctx.check()
    return "\n".join(result)
