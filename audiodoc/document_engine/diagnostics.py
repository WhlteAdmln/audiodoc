# Copyright (c) 2026 Nikolai Zelensky
"""Shared diagnostics for native document-processing tools."""

import logging
import shutil
from dataclasses import dataclass

from audiodoc.document_engine.extractors.djvu.tools import DjvuTools, find_djvu_tools
from audiodoc.document_engine.ocr.tesseract import _get_pytesseract

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class NativeToolsStatus:
    """Describe the availability of native document-processing tools."""

    tesseract: str | None
    languages: tuple[str, ...]
    djvu_tools: DjvuTools

    @property
    def djvulibre(self) -> bool:
        """Return whether all required DjVuLibre executables are available."""
        return all(
            (
                self.djvu_tools.djvutxt,
                self.djvu_tools.djvused,
                self.djvu_tools.ddjvu,
            )
        )


def check_native_tools() -> NativeToolsStatus:
    """Inspect Tesseract and DjVuLibre without failing on missing tools."""
    tesseract = shutil.which("tesseract")
    languages: tuple[str, ...] = ()

    if tesseract is not None:
        try:
            pytesseract = _get_pytesseract()
        except ImportError:
            logger.warning("Unable to query Tesseract language data")
        else:
            try:
                languages = tuple(sorted(set(pytesseract.get_languages(config=""))))
            except (OSError, pytesseract.TesseractError):
                logger.warning("Unable to query Tesseract language data")

    return NativeToolsStatus(
        tesseract=tesseract,
        languages=languages,
        djvu_tools=find_djvu_tools(),
    )
