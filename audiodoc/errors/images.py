# Copyright (c) 2026 Nikolai Zelensky
"""Client-safe exceptions raised while recognizing images with OCR."""

from audiodoc.errors.documents import DocumentRejectedError
from audiodoc.errors.messages import ERROR_MESSAGES


class EmptyImageError(DocumentRejectedError):
    """Raised when OCR receives empty image data."""

    public_message = ERROR_MESSAGES["empty_image"]


class UnknownImageFormatError(DocumentRejectedError):
    """Raised when the image format cannot be identified."""

    public_message = ERROR_MESSAGES["unknown_image_format"]


class UnsupportedOcrImageFormatError(DocumentRejectedError):
    """Raised when an image format is unsupported by OCR."""

    public_message = ERROR_MESSAGES["unsupported_ocr_image_format"]


class ImageTooLargeError(DocumentRejectedError):
    """Raised when an image exceeds the OCR pixel limit."""

    public_message = ERROR_MESSAGES["image_too_large"]


class TooManyImageFramesError(DocumentRejectedError):
    """Raised when an image contains more frames than allowed."""

    public_message = ERROR_MESSAGES["too_many_image_frames"]


class ImageRecognitionFailedError(DocumentRejectedError):
    """Raised when Tesseract cannot recognize an image page."""

    public_message = ERROR_MESSAGES["image_recognition_failed"]
