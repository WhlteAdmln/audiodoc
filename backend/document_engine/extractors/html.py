# Copyright (c) 2026 Nikolai Zelensky
"""Extract readable text from HTML without scripts, styles, and navigation."""

from bs4 import BeautifulSoup

from backend.document_engine.extractors.base import ExtractContext, make_context


def extract_html(data: bytes, *, context: ExtractContext | None = None) -> str:
    """Extract HTML text and stop at the shared character budget."""
    ctx = make_context(context)
    ctx.check()
    soup = BeautifulSoup(data, "html.parser")
    for element in soup(["script", "style", "noscript"]):
        element.decompose()
    ctx.check()
    return ctx.budget.add(soup.get_text(separator="\n", strip=True))
