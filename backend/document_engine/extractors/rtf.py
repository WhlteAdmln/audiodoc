"""Extract readable text from Rich Text Format documents."""

from striprtf.striprtf import rtf_to_text

from backend.document_engine.extractors.base import ExtractContext, make_context


def extract_rtf(data: bytes, *, context: ExtractContext | None = None) -> str:
    """Convert RTF to plain text and apply the remaining output budget."""
    ctx = make_context(context)
    ctx.check()
    text = rtf_to_text(data.decode("utf-8", errors="replace"))
    ctx.check()
    return ctx.budget.add(text)
