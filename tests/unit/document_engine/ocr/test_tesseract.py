# Copyright (c) 2026 Nikolai Zelensky

"""Tests for ocr tesseract."""

from pathlib import Path

import pytest
from PIL import Image
from pytesseract import TesseractError

from audiodoc.document_engine.ocr.tesseract import ensure_ready, pytesseract
from audiodoc.errors.documents import DependencyMissingError
from tests.support.tesseract import FakeTesseract


@pytest.fixture(name="tesseract")
def fixture_tesseract(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> FakeTesseract:
    """Put a fake Tesseract alone on PATH and forget earlier readiness checks."""
    fake = FakeTesseract(tmp_path)
    monkeypatch.setenv("PATH", str(fake.bin_dir))
    ensure_ready.cache_clear()
    return fake


def _readiness_error(languages: str) -> str:
    with pytest.raises(DependencyMissingError) as caught:
        ensure_ready(languages)
    return str(caught.value)


def _recognize(languages: str, timeout: float = 5) -> str:
    with Image.new("L", (5, 3), color=200) as image:
        return pytesseract.image_to_string(
            image, lang=languages, config="--psm 3", timeout=timeout
        )


def test_requires_the_tesseract_binary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    empty_bin = tmp_path / "empty-bin"
    empty_bin.mkdir()
    monkeypatch.setenv("PATH", str(empty_bin))
    ensure_ready.cache_clear()

    message = _readiness_error("rus+eng")

    expected = "На сервере не установлена нужная программа"
    assert message == expected, "a missing Tesseract binary was not reported"


def test_reports_a_missing_language(tesseract: FakeTesseract) -> None:
    tesseract.configure(languages=["eng"])

    message = _readiness_error("rus+eng")

    expected = "На сервере не установлена нужная программа"
    assert message == expected, "a missing language was not reported"


def test_reports_an_unreadable_language_list(tesseract: FakeTesseract) -> None:
    tesseract.configure(languages_exit_code=2)

    message = _readiness_error("deu+fra")

    expected = "На сервере не установлена нужная программа"
    assert message == expected, "an unreadable language list was not reported"


@pytest.mark.usefixtures("tesseract")
@pytest.mark.parametrize(
    "languages", ["eng;rm -rf /", "../../tessdata/eng", "ENG", "eng rus"]
)
def test_rejects_language_expressions_that_name_no_installed_language(
    languages: str,
) -> None:
    message = _readiness_error(languages)

    expected = "На сервере не установлена нужная программа"
    assert message == expected, "an unknown language expression was accepted"


def test_checks_each_language_expression_once(tesseract: FakeTesseract) -> None:
    for _ in range(5):
        ensure_ready("rus+eng")

    expected_queries = 1
    assert tesseract.language_queries == expected_queries, "the check was repeated"


def test_retries_a_failed_check(tesseract: FakeTesseract) -> None:
    tesseract.configure(languages=["eng"])
    with pytest.raises(DependencyMissingError):
        ensure_ready("rus+eng")
    tesseract.configure(languages=["eng", "rus"])

    ensure_ready("rus+eng")

    expected_queries = 2
    assert tesseract.language_queries == expected_queries, "a failure was cached"


def test_passes_languages_and_config_as_separate_arguments(
    tesseract: FakeTesseract,
) -> None:
    _recognize("rus+eng")

    expected_arguments = ["stdout", "-l", "rus+eng", "--psm", "3"]
    assert tesseract.recognitions[0][1:] == expected_arguments, "wrong arguments"


def test_passes_a_hostile_language_expression_as_one_argument(
    tesseract: FakeTesseract,
) -> None:
    _recognize("eng --tessdata-dir /tmp; id")

    expected_arguments = ["stdout", "-l", "eng --tessdata-dir /tmp; id"]
    assert tesseract.recognitions[0][1:4] == expected_arguments, "argument split"


def test_omits_the_language_option_without_languages(
    tesseract: FakeTesseract,
) -> None:
    _recognize("")

    expected_arguments = ["stdout", "--psm", "3"]
    assert tesseract.recognitions[0][1:] == expected_arguments, "empty -l was passed"


def test_returns_recognized_text(tesseract: FakeTesseract) -> None:
    tesseract.configure(pages=["Распознано 42\n".encode()])

    text = _recognize("rus")

    expected_text = "Распознано 42\n"
    assert text == expected_text, "the recognized text changed"


def test_removes_the_image_file_after_recognition(tesseract: FakeTesseract) -> None:
    _recognize("eng")

    image_directory = Path(tesseract.recognitions[0][0]).parent
    assert image_directory.exists() is False, "the OCR input image was left behind"


def test_reports_a_failing_tesseract_run(tesseract: FakeTesseract) -> None:
    tesseract.configure(exit_code=3, stderr="Error opening data file")

    with pytest.raises(TesseractError) as caught:
        _recognize("eng")

    expected_status = 3
    assert caught.value.status == expected_status, "the exit status was lost"


def test_reports_output_that_is_not_utf8(tesseract: FakeTesseract) -> None:
    tesseract.configure(pages=[b"Seite \xff\xfe 17"])

    with pytest.raises(RuntimeError) as caught:
        _recognize("deu")

    expected_message = "Tesseract output is not valid UTF-8"
    assert str(caught.value) == expected_message, "invalid UTF-8 was not reported"


def test_reports_a_timeout(tesseract: FakeTesseract) -> None:
    tesseract.configure(delay=10)

    with pytest.raises(RuntimeError) as caught:
        _recognize("eng", timeout=0.3)

    expected_message = "Tesseract process timeout"
    assert str(caught.value) == expected_message, "a hung Tesseract was not stopped"
