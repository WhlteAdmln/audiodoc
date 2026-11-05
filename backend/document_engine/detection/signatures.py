"""Проверки сигнатур документов."""


def detect_pdf_signature(data: bytes) -> str | None:
    """Return ``pdf`` when the payload starts with the PDF file signature.

    Args:
        data: Leading bytes of the uploaded document.

    Returns:
        ``pdf`` on a match, otherwise ``None``.
    """
    if data.startswith(b"%PDF-"):
        return "pdf"
    return None


def detect_djvu_signature(data: bytes) -> str | None:
    """Return ``djvu`` when the payload starts with the DjVu container marker.

    Args:
        data: Leading bytes of the uploaded document.

    Returns:
        ``djvu`` on a match, otherwise ``None``.
    """
    if data.startswith(b"AT&TFORM"):
        return "djvu"
    return None


def detect_ole_signature(
    data: bytes,
    file_extension: str,
) -> str | None:
    """Определяет старые форматы Office в OLE Compound File."""
    if not data.startswith(bytes.fromhex("D0CF11E0A1B11AE1")):
        return None

    if file_extension == ".doc":
        return "doc"
    if file_extension == ".xls":
        return "xls"
    if file_extension == ".ppt":
        return "ppt"
    return "ole"


def detect_rtf_signature(data: bytes) -> str | None:
    """Return ``rtf`` when the payload begins with an RTF header.

    Args:
        data: Leading bytes of the uploaded document.

    Returns:
        ``rtf`` on a match, otherwise ``None``.
    """
    if data.startswith(b"{\\rtf"):
        return "rtf"
    return None
