# Copyright (c) 2026 Nikolai Zelensky
"""Check Tesseract and the requested language data once per process."""

import importlib
import shlex
import shutil
import tempfile
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, cast

if TYPE_CHECKING:
    from PIL import Image

from backend.common.subprocess_runner import SubprocessTimeoutError, run_limited
from backend.errors.documents import DependencyMissingError


class _Pytesseract(Protocol):
    """Describe the pytesseract API used by the OCR pipeline."""

    TesseractError: type[Exception]

    def get_languages(self, config: str = "") -> list[str]:
        """Return available OCR languages.

        Args:
            config: Additional Tesseract configuration.

        """
        ...

    def image_to_string(
        self,
        image: "Image.Image",
        *,
        lang: str,
        config: str,
        timeout: float,
    ) -> str:
        """Recognize text in an image.

        Args:
            image: Image to recognize.
            lang: OCR languages to use.
            config: Additional Tesseract configuration.
            timeout: Maximum execution time in seconds.

        """
        ...


def _get_pytesseract() -> _Pytesseract:
    """Return the lazily imported pytesseract module."""
    return cast("_Pytesseract", importlib.import_module("pytesseract"))


def _get_tesseract_command() -> str:
    """Return the configured Tesseract executable path."""
    module = importlib.import_module("pytesseract.pytesseract")
    return cast("str", module.tesseract_cmd)


class _PytesseractProxy:
    """Provide lazy access to the pytesseract API."""

    def get_languages(self, config: str = "") -> list[str]:
        """Return available OCR languages."""
        return _get_pytesseract().get_languages(config=config)

    def image_to_string(
        self,
        image: "Image.Image",
        *,
        lang: str,
        config: str,
        timeout: float,
    ) -> str:
        """Recognize text using a bounded subprocess."""
        with tempfile.TemporaryDirectory(prefix="audiodoc-ocr-") as directory:
            image_path = Path(directory) / "input.png"
            image.save(image_path, format="PNG")

            args = [
                _get_tesseract_command(),
                str(image_path),
                "stdout",
            ]
            if lang:
                args.extend(["-l", lang])
            args.extend(shlex.split(config))

            try:
                return_code, output, stderr = run_limited(
                    args,
                    timeout=timeout,
                )
            except SubprocessTimeoutError as error:
                message = "Tesseract process timeout"
                raise RuntimeError(message) from error

            if return_code:
                message = stderr.decode("utf-8", errors="replace")
                raise _get_pytesseract().TesseractError(return_code, message)

            return output.decode("utf-8")


pytesseract = _PytesseractProxy()


DEFAULT_OCR_LANGUAGES = "rus+eng"


def _check_tesseract() -> None:
    """Raise a safe dependency error when the Tesseract executable is absent."""
    if shutil.which("tesseract") is None:
        raise DependencyMissingError


def _check_languages(languages: str) -> None:
    """Raise a safe dependency error when requested language data is absent."""
    try:
        available = set(pytesseract.get_languages(config=""))
    except Exception as error:
        raise DependencyMissingError from error

    requested = {language for language in languages.split("+") if language}
    missing = requested - available
    if missing:
        raise DependencyMissingError


@lru_cache(maxsize=8)
def ensure_ready(languages: str) -> None:
    """Check the executable and language data once for each language expression.

    ``lru_cache`` stores only successful return values; failed checks are retried
    on the next request, allowing an administrator to install missing language
    packages without restarting the backend.
    """
    _check_tesseract()
    _check_languages(languages)
