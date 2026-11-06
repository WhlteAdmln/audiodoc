"""Check Tesseract and the requested language data once per process."""

import shutil
from functools import lru_cache

import pytesseract

from backend.errors.documents import DependencyMissingError

DEFAULT_OCR_LANGUAGES = "rus+eng"


def _check_tesseract() -> None:
    """Raise a safe dependency error when the Tesseract executable is absent."""
    if shutil.which("tesseract") is None:
        raise DependencyMissingError()


def _check_languages(languages: str) -> None:
    """Raise a safe dependency error when requested language files are absent."""
    try:
        available = set(pytesseract.get_languages(config=""))
    except Exception as error:
        raise DependencyMissingError() from error

    requested = {language for language in languages.split("+") if language}
    missing = requested - available
    if missing:
        raise DependencyMissingError()


@lru_cache(maxsize=8)
def ensure_ready(languages: str) -> None:
    """Check the executable and language data once for each language expression.

    ``lru_cache`` stores only successful return values; failed checks are retried
    on the next request, allowing an administrator to install missing language
    packages without restarting the backend.
    """
    _check_tesseract()
    _check_languages(languages)
