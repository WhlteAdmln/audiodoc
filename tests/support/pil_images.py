# Copyright (c) 2026 Nikolai Zelensky
"""Images for OCR tests: encoded files, crafted headers and fake Pillow frames."""

import io
import struct
import zlib
from typing import Never

from PIL import Image

_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


class UnexpectedImageCopyError(AssertionError):
    """Raised when OCR copies an oversized image frame."""

    def __init__(self) -> None:
        """Initialize the test assertion error."""
        super().__init__("copy must not be called for oversized frames")


class OversizedImage:
    """Describe a one-frame 100 by 100 pixel image that must not be copied."""

    n_frames = 1
    width = 100
    height = 100

    @staticmethod
    def seek(_index: object) -> None:
        """Accept any frame index."""
        return

    @staticmethod
    def copy() -> Never:
        """Fail because an oversized frame must be rejected before the copy."""
        raise UnexpectedImageCopyError


def encoded_image(image_format: str, size: tuple[int, int] = (4, 4)) -> bytes:
    """Return a white RGB image of the given size encoded in one format."""
    output = io.BytesIO()
    with Image.new("RGB", size, color="white") as image:
        image.save(output, format=image_format)
    return output.getvalue()


def multi_page_tiff(pages: int) -> bytes:
    """Return a TIFF file with the given number of small grayscale pages."""
    frames = [Image.new("L", (3, 2), color=40 * index) for index in range(pages)]
    output = io.BytesIO()
    frames[0].save(output, format="TIFF", save_all=True, append_images=frames[1:])
    for frame in frames:
        frame.close()
    return output.getvalue()


def png_header(width: int, height: int) -> bytes:
    """Return a PNG whose header declares a size its empty pixel data lacks."""

    def chunk(kind: bytes, data: bytes) -> bytes:
        checksum = struct.pack(">I", zlib.crc32(kind + data))
        return struct.pack(">I", len(data)) + kind + data + checksum

    header = struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0)
    return (
        _PNG_SIGNATURE
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(b""))
        + chunk(b"IEND", b"")
    )
