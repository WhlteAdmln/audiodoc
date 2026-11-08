# Copyright (c) 2026 Nikolai Zelensky
"""Extract paragraphs and table rows from Microsoft Word documents."""

from io import BytesIO

from docx import Document

from backend.document_engine.extractors.base import (
    ExtractContext,
    add_chunk,
    make_context,
)


def extract_docx(data: bytes, *, context: ExtractContext | None = None) -> str:
    """Extract DOCX paragraphs and table rows while respecting the text budget."""
    ctx = make_context(context)
    document = Document(BytesIO(data))
    result: list[str] = []

    for paragraph in document.paragraphs:
        ctx.check()
        text = paragraph.text.strip()
        if text:
            add_chunk(result, ctx, text)
        if ctx.budget.truncated:
            return "\n".join(result)

    for table in document.tables:
        for row in table.rows:
            ctx.check()
            cells = [cell.text.strip() for cell in row.cells]
            line = " | ".join(cells)
            if line.strip():
                add_chunk(result, ctx, line)
            if ctx.budget.truncated:
                return "\n".join(result)
    return "\n".join(result)
