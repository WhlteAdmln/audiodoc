"""Extract slide and table text from PowerPoint within the shared text budget."""

from io import BytesIO

from pptx import Presentation

from backend.document_engine.extractors.base import (
    ExtractContext,
    add_chunk,
    make_context,
)


def extract_pptx(data: bytes, *, context: ExtractContext | None = None) -> str:
    """Extract PPTX slide text without repeatedly summing the growing result."""
    ctx = make_context(context)
    presentation = Presentation(BytesIO(data))
    result: list[str] = []

    for index, slide in enumerate(presentation.slides):
        ctx.check()
        add_chunk(result, ctx, f"--- Слайд {index + 1} ---")
        if ctx.budget.is_truncated():
            break

        for shape in slide.shapes:
            ctx.check()
            if shape.has_text_frame:
                text = shape.text.strip()
                if text:
                    add_chunk(result, ctx, text)
            if shape.has_table and not ctx.budget.is_truncated():
                for row in shape.table.rows:
                    ctx.check()
                    line = " | ".join(cell.text.strip() for cell in row.cells)
                    if line:
                        add_chunk(result, ctx, line)
                    if ctx.budget.is_truncated():
                        break
            if ctx.budget.is_truncated():
                break
        if ctx.budget.is_truncated():
            break

    ctx.check()
    return "\n".join(result)
