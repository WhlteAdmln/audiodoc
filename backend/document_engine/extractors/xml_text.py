"""Extract non-empty text nodes from XML within the shared text budget."""

from backend.document_engine.extractors.base import (
    ExtractContext,
    add_chunk,
    make_context,
)
from backend.document_engine.guards.xml_safe import parse_xml


def extract_xml_text(data: bytes, *, context: ExtractContext | None = None) -> str:
    """Extract XML text nodes in document order with deadline checks."""
    ctx = make_context(context)
    root = parse_xml(data)
    result: list[str] = []
    for element in root.iter():
        ctx.check()
        if element.text and element.text.strip():
            add_chunk(result, ctx, element.text.strip())
        if ctx.budget.truncated:
            break
    return "\n".join(result)
