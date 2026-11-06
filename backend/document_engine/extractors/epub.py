"""Extract readable chapter text from EPUB packages."""

import io
from pathlib import Path

from bs4 import BeautifulSoup
from ebooklib import ITEM_DOCUMENT, epub

from backend.document_engine.extractors.base import (
    ExtractContext,
    add_chunk,
    make_context,
)


def extract_epub(data: bytes, *, context: ExtractContext | None = None) -> str:
    """Extract EPUB content incrementally, skipping navigation and service items."""
    ctx = make_context(context)
    book = epub.read_epub(io.BytesIO(data))
    result: list[str] = []

    for item in book.get_items_of_type(ITEM_DOCUMENT):
        ctx.check()
        name = item.get_name().lower()
        properties = getattr(item, "properties", [])
        if "nav" in properties or "nav" in Path(name).stem.lower():
            continue

        soup = BeautifulSoup(item.get_content(), "html.parser")
        for element in soup(["script", "style", "nav"]):
            element.decompose()
        text = soup.get_text(separator="\n", strip=True)
        if text:
            add_chunk(result, ctx, text, separator_length=2)
        if ctx.budget.truncated:
            break
    return "\n\n".join(result)
