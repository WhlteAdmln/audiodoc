# Copyright (c) 2026 Nikolai Zelensky
"""Client-safe exceptions raised while extracting DJVU documents."""

from audiodoc.errors.documents import DocumentRejectedError, ProcessingTimeoutError
from audiodoc.errors.messages import ERROR_MESSAGES


class DjvuOutputTooLargeError(DocumentRejectedError):
    """Raised when a DjVuLibre command produces excessive output."""

    public_message = ERROR_MESSAGES["djvu_output_too_large"]


class DjvuProcessingTimeoutError(ProcessingTimeoutError):
    """Raised when a DjVuLibre command exceeds its processing deadline."""

    public_message = ERROR_MESSAGES["djvu_processing_timeout"]


class DjvuPageCountUnavailableError(DocumentRejectedError):
    """Raised when the DjVu page count cannot be determined."""

    public_message = ERROR_MESSAGES["djvu_page_count_unavailable"]


class InvalidDjvuPageCountError(DocumentRejectedError):
    """Raised when the DjVu page count is malformed."""

    public_message = ERROR_MESSAGES["invalid_djvu_page_count"]


class DjvuNoPagesError(DocumentRejectedError):
    """Raised when a DjVu document contains no pages."""

    public_message = ERROR_MESSAGES["djvu_no_pages"]


class DjvuTooManyPagesError(DocumentRejectedError):
    """Raised when a DjVu document exceeds the page limit."""

    public_message = ERROR_MESSAGES["djvu_too_many_pages"]


class DjvuPageRenderError(DocumentRejectedError):
    """Raised when a DjVu page cannot be rendered."""

    public_message = ERROR_MESSAGES["djvu_page_render_failed"]


class DjvuPageTooLargeError(DocumentRejectedError):
    """Raised when a rendered DjVu page exceeds the OCR size limit."""

    public_message = ERROR_MESSAGES["djvu_page_too_large"]


class DjvuTextTooLargeError(DocumentRejectedError):
    """Raised when the embedded DjVu text layer exceeds its size limit."""

    public_message = ERROR_MESSAGES["djvu_text_too_large"]


class DjvuTextLayerTimeoutError(ProcessingTimeoutError):
    """Raised when extracting the DjVu text layer exceeds its deadline."""

    public_message = ERROR_MESSAGES["djvu_text_layer_timeout"]


class DjvuTextLayerReadError(DocumentRejectedError):
    """Raised when the embedded DjVu text layer cannot be read."""

    public_message = ERROR_MESSAGES["djvu_text_layer_read_failed"]
