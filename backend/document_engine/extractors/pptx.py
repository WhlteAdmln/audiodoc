# Copyright (c) 2026 Nikolai Zelensky
"""Extract slide and table text from PowerPoint within the shared text budget."""

from io import BytesIO
from typing import TYPE_CHECKING, cast

from pptx import Presentation
from pptx.shapes.base import BaseShape
from pptx.slide import Slide

if TYPE_CHECKING:
    from pptx.shapes.autoshape import Shape
    from pptx.shapes.graphfrm import GraphicFrame

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
        if _extract_slide_text(slide, index + 1, ctx, result):
            break

    ctx.check()
    return "\n".join(result)


def _extract_slide_text(
    slide: Slide,
    slide_number: int,
    ctx: ExtractContext,
    result: list[str],
) -> bool:
    ctx.check()
    add_chunk(result, ctx, f"--- Слайд {slide_number} ---")
    if ctx.budget.is_truncated():
        return True

    for shape in slide.shapes:
        ctx.check()
        _extract_shape_text(shape, ctx, result)
        if ctx.budget.is_truncated():
            return True

    return False


def _extract_shape_text(
    shape: BaseShape,
    ctx: ExtractContext,
    result: list[str],
) -> None:
    if shape.has_text_frame:
        text = cast("Shape", shape).text.strip()
        if text:
            add_chunk(result, ctx, text)

    if shape.has_table and not ctx.budget.is_truncated():
        for row in cast("GraphicFrame", shape).table.rows:
            ctx.check()
            line = " | ".join(cell.text.strip() for cell in row.cells)
            if line:
                add_chunk(result, ctx, line)
            if ctx.budget.is_truncated():
                break
