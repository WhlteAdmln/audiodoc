"""Подготовка изображений перед распознаванием текста."""

from PIL import Image, ImageOps

from backend.document_engine.limits import MAX_IMAGE_PIXELS
from backend.errors.documents import DocumentRejectedError

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
        raise DocumentRejectedError(
            "Изображение слишком большое: превышен лимит пикселей"
        )

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

    # Переводим в оттенки серого.
    image = ImageOps.grayscale(image)

    # Улучшаем контраст.
    image = ImageOps.autocontrast(image)

    return image
