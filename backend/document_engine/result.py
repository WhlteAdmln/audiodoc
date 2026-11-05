"""Build stable document responses and retain the extraction truncation flag."""

from backend.document_engine.limits import MAX_EXTRACTED_TEXT_LENGTH


def limit_text(text: str) -> str:
    """Keep a legacy final safety cap for text created outside TextBudget."""
    if len(text) > MAX_EXTRACTED_TEXT_LENGTH:
        return text[:MAX_EXTRACTED_TEXT_LENGTH]
    return text


def build_result(filetype: str, text: str, *, truncated: bool = False) -> dict:
    """Create the public document result, including whether extraction was cut."""
    text = limit_text(text.strip())
    return {
        "format": filetype,
        "text": text,
        "characters": len(text),
        "truncated": bool(truncated),
    }
