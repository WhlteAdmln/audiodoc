# Copyright (c) 2026 Nikolai Zelensky
"""Document format detection by content and extension."""

from pathlib import Path

from audiodoc.document_engine.detection.formats import (
    IMAGE_EXTENSIONS,
    SUPPORTED_FORMATS,
    extension_map,
)
from audiodoc.document_engine.detection.signatures import (
    detect_djvu_signature,
    detect_ole_signature,
    detect_pdf_signature,
    detect_rtf_signature,
)
from audiodoc.document_engine.detection.text_probe import looks_like_text
from audiodoc.document_engine.detection.zip_formats import _detect_zip_format


def detect_format(
    data: bytes,
    filename: str | None = None,
) -> str | None:
    """Determine the document format.

    The detection order is preserved: image extension, PDF/DJVU/OLE signatures,
    ZIP, RTF, extension, and text-content detection.

    Standalone images are not processed; they are routed to the separate
    Vision Engine.
    """
    detected: str | None = None
    if data:
        file_extension = Path(filename or "").suffix.lower()

        # Images are handled by the separate Vision Engine.
        if file_extension not in IMAGE_EXTENSIONS:
            detected = detect_pdf_signature(data)
            if not detected:
                detected = detect_djvu_signature(data)
            if not detected:
                detected = detect_ole_signature(data, file_extension)

            # ZIP containers: DOCX, XLSX, PPTX, EPUB, ODT, and others.
            if not detected and data.startswith(b"PK"):
                detected = _detect_zip_format(data)

            if not detected:
                detected = detect_rtf_signature(data)

            # Text formats: check the extension.
            if not detected:
                extension = file_extension.lstrip(".")
                if extension in extension_map:
                    detected = extension_map[extension]
                # Check whether the content looks like text.
                elif looks_like_text(data):
                    detected = "txt"

    return detected


__all__ = [
    "IMAGE_EXTENSIONS",
    "SUPPORTED_FORMATS",
    "detect_format",
]
