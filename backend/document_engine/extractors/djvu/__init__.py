"""Extract DJVU text with bounded tools and page-by-page OCR fallback."""

import logging
import tempfile
from pathlib import Path

from backend.common.deadline import Deadline
from backend.document_engine.extractors.base import ExtractContext, make_context
from backend.document_engine.extractors.djvu.ocr_pages import extract_ocr_pages
from backend.document_engine.extractors.djvu.text_layer import extract_text_layer
from backend.document_engine.extractors.djvu.tools import (
    find_djvu_tools,
    require_djvutxt,
)
from backend.errors.documents import DependencyMissingError

logger = logging.getLogger(__name__)


def extract_djvu(
    data: bytes,
    *,
    context: ExtractContext | None = None,
    deadline: Deadline | None = None,
) -> str:
    """Extract the DJVU text layer first, then use bounded rendering and OCR."""
    ctx = make_context(context, deadline=deadline)
    ctx.check()
    tools = find_djvu_tools()
    djvutxt = require_djvutxt(tools)

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        file_path = temp_path / "document.djvu"
        file_path.write_bytes(data)

        text = extract_text_layer(file_path, djvutxt, context=ctx)
        if text:
            return ctx.budget.add(text)

        logger.info("DJVU has no text layer; starting OCR")
        if tools.djvused is None or tools.ddjvu is None:
            raise DependencyMissingError()
        return extract_ocr_pages(
            file_path,
            temp_path,
            tools.djvused,
            tools.ddjvu,
            context=ctx,
        )


__all__ = ["extract_djvu"]
