# Copyright (c) 2026 Nikolai Zelensky
import importlib
import shutil
import subprocess
from io import BytesIO
from typing import Protocol, cast

import pytest
from PIL import Image

from audiodoc.document_engine.extractors.djvu import extract_djvu
from tests.builders import create_ocr_image

pytestmark = pytest.mark.integration


class _PytesseractModule(Protocol):
    TesseractError: type[Exception]

    def get_languages(self, config: str = "") -> list[str]: ...


def test_scanned_djvu_is_processed_with_ocr(tmp_path):
    required = ("c44", "djvutxt", "djvused", "ddjvu", "tesseract")
    tool_paths: dict[str, str] = {}
    for name in required:
        executable = shutil.which(name)
        if executable is not None:
            tool_paths[name] = executable

    missing = [name for name in required if name not in tool_paths]
    if missing:
        pytest.skip("Missing DJVU/OCR tools: " + ", ".join(missing))

    try:
        pytesseract = cast(
            "_PytesseractModule",
            importlib.import_module("pytesseract"),
        )
    except ImportError as error:
        pytest.skip(f"Tesseract languages are unavailable: {error}")

    try:
        languages = set(pytesseract.get_languages(config=""))
    except (OSError, pytesseract.TesseractError) as error:
        pytest.skip(f"Tesseract languages are unavailable: {error}")

    if not {"rus", "eng"}.issubset(languages):
        pytest.skip("Tesseract language packs rus and eng are required")

    image = Image.open(BytesIO(create_ocr_image())).convert("RGB")
    ppm_path = tmp_path / "scanned.ppm"
    djvu_path = tmp_path / "scanned.djvu"
    image.save(ppm_path)
    image.close()

    subprocess.run(  # noqa: S603 - resolved c44 runs with a fixed argument list.
        [tool_paths["c44"], str(ppm_path), str(djvu_path)],
        check=True,
        capture_output=True,
        timeout=60,
    )

    text = extract_djvu(djvu_path.read_bytes())

    assert "Document Engine" in text
    assert "Hello" in text
