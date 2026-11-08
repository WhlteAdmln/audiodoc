"""Extract text blocks from FictionBook 2 documents."""

import xml.etree.ElementTree as ET
from collections.abc import Iterator

from backend.document_engine.extractors.base import (
    ExtractContext,
    add_chunk,
    make_context,
)
from backend.document_engine.guards.xml_safe import parse_xml
from backend.errors.documents import DocumentRejectedError

BLOCK_TAGS = {"title", "subtitle", "p", "v", "text-author", "date"}


def _iter_text_blocks(element: ET.Element) -> Iterator[str]:
    """Yield text in block-aware order without constructing a whole-book string."""
    tag = element.tag.split("}")[-1]
    if tag in BLOCK_TAGS:
        text = "".join(element.itertext()).strip()
        if text:
            yield text
        return

    if element.text and element.text.strip():
        yield element.text.strip()
    for child in element:
        yield from _iter_text_blocks(child)
        if child.tail and child.tail.strip():
            yield child.tail.strip()


def extract_fb2(data: bytes, *, context: ExtractContext | None = None) -> str:
    """Extract FB2 block text, checking the deadline and budget as it walks."""
    ctx = make_context(context)
    root = parse_xml(data)
    bodies = [item for item in root.iter() if item.tag.split("}")[-1] == "body"]
    if not bodies:
        raise DocumentRejectedError("В FB2 не найдено содержимое книги")

    result: list[str] = []
    for body in bodies:
        for text in _iter_text_blocks(body):
            ctx.check()
            add_chunk(result, ctx, text)
            if ctx.budget.truncated:
                return "\n".join(result)
    return "\n".join(result)
