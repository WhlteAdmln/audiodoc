"""Подготовка изображений перед распознаванием текста."""

from PIL import Image, ImageOps

from backend.document_engine.limits import MAX_IMAGE_PIXELS
from backend.errors.documents import DocumentRejectedError


class _ImageTooLargeError(DocumentRejectedError):
    """Raised when an image exceeds the OCR pixel limit."""

    public_message = "Изображение слишком большое: превышен лимит пикселей"


SUPPORTED_IMAGE_FORMATS = {
    "PNG",
    "JPEG",
    "TIFF",
    "BMP",
    "WEBP",
}


def _prepare_image(image: Image.Image) -> Image.Image:
    """Подготавливает изображение для OCR."""
    if image.width * image.height > MAX_IMAGE_PIXELS:
        raise _ImageTooLargeError

    # Исправляем ориентацию по EXIF.
    image = ImageOps.exif_transpose(image)

    # Учитываем прозрачность.
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

    # Улучшаем контраст.
    return ImageOps.autocontrast(image)
