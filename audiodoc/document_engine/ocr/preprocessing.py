# Copyright (c) 2026 Nikolai Zelensky
"""Prepare images before text recognition."""

from PIL import Image, ImageOps

from audiodoc.document_engine.limits import MAX_IMAGE_PIXELS
from audiodoc.errors.documents import DocumentRejectedError
from audiodoc.errors.messages import ERROR_MESSAGES


class _ImageTooLargeError(DocumentRejectedError):
    """Raised when an image exceeds the OCR pixel limit."""

    public_message = ERROR_MESSAGES["image_too_large"]


SUPPORTED_IMAGE_FORMATS = {
    "PNG",
    "JPEG",
    "TIFF",
    "BMP",
    "WEBP",
}


def _prepare_image(image: Image.Image) -> Image.Image:
    """Prepare an image for OCR."""
    if image.width * image.height > MAX_IMAGE_PIXELS:
        raise _ImageTooLargeError

    # Correct the EXIF orientation.
    image = ImageOps.exif_transpose(image)

    # Handle transparency.
    if image.mode in ("RGBA", "LA"):
        rgba = image.convert("RGBA")
        background = Image.new(
            "RGBA",
            rgba.size,
            "white",
        )
        image = Image.alpha_composite(
            background,
            rgba,
        ).convert("RGB")
    else:
        image = image.convert("RGB")

    # Convert the image to grayscale.
    image = ImageOps.grayscale(image)

    # Improve contrast.
    return ImageOps.autocontrast(image)
