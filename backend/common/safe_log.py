"""Sanitize untrusted values before writing them to application logs."""


def log_safe(value: object | None, limit: int = 120) -> str:
    """Return a short, single-line, printable representation of a value.

    Args:
        value: Untrusted value to include in a log record.
        limit: Maximum number of characters in the returned representation.

    Returns:
        A sanitized string with control characters replaced.
    """
    text = "" if value is None else str(value)
    text = text.replace("\r", "\\r").replace("\n", "\\n")
    text = "".join(ch if ch.isprintable() else "?" for ch in text)
    return text[:limit]
