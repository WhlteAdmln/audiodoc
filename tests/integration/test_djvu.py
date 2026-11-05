import shutil
import subprocess

import pytest

pytestmark = pytest.mark.integration

from backend.document_engine.extractors.djvu import extract_djvu
from tests.builders import create_ocr_image


def test_scanned_djvu_is_processed_with_ocr(tmp_path):
    required = ("c44", "djvutxt", "djvused", "ddjvu", "tesseract")
    missing = [name for name in required if shutil.which(name) is None]
    if missing:
        pytest.skip("Missing DJVU/OCR tools: " + ", ".join(missing))

    import pytesseract

    try:
        languages = set(pytesseract.get_languages(config=""))
    except Exception as error:
        pytest.skip(f"Tesseract languages are unavailable: {error}")

    if not {"rus", "eng"}.issubset(languages):
        pytest.skip("Tesseract language packs rus and eng are required")

    from PIL import Image
    from io import BytesIO

    image = Image.open(BytesIO(create_ocr_image())).convert("RGB")
    ppm_path = tmp_path / "scanned.ppm"
    djvu_path = tmp_path / "scanned.djvu"
    image.save(ppm_path)
    image.close()

    subprocess.run(
        ["c44", str(ppm_path), str(djvu_path)],
        check=True,
        capture_output=True,
        timeout=60,
    )

    text = extract_djvu(djvu_path.read_bytes())

    assert "Document Engine" in text
    assert "Hello" in text
