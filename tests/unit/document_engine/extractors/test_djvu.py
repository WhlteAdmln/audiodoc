# Copyright (c) 2026 Nikolai Zelensky
"""Unit tests for bounded DJVU text extraction and page rendering."""

from pathlib import Path

import pytest

from audiodoc.common.deadline import Deadline, DeadlineExceededError
from audiodoc.common.text_budget import TextBudget
from audiodoc.document_engine.extractors.base import ExtractContext
from audiodoc.document_engine.extractors.djvu import extract_djvu
from audiodoc.document_engine.extractors.djvu import ocr_pages as ocr_pages_module
from audiodoc.document_engine.extractors.djvu import text_layer as text_layer_module
from audiodoc.document_engine.extractors.djvu.ocr_pages import extract_ocr_pages
from audiodoc.document_engine.limits import DJVU_RENDER_MAX_SIZE, MAX_DOCUMENT_PAGES
from audiodoc.document_engine.ocr.tesseract import ensure_ready
from audiodoc.errors.base import AppError
from tests.support.djvulibre import FakeDjvuLibre, ToolBehavior
from tests.support.tesseract import FakeTesseract

_DJVU = b"AT&TFORM\x00\x00\x00\x08DJVUINFO"


@pytest.fixture(name="djvulibre")
def fixture_djvulibre(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> FakeDjvuLibre:
    """Put fake DjVuLibre tools alone on PATH."""
    fake = FakeDjvuLibre(tmp_path)
    monkeypatch.setenv("PATH", str(fake.bin_dir))
    return fake


@pytest.fixture(name="tesseract")
def fixture_tesseract(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> FakeTesseract:
    """Add a fake Tesseract to the same PATH directory and forget earlier checks."""
    fake = FakeTesseract(tmp_path)
    monkeypatch.setenv("PATH", str(fake.bin_dir))
    ensure_ready.cache_clear()
    return fake


@pytest.fixture(name="scanned")
def fixture_scanned(
    djvulibre: FakeDjvuLibre, tesseract: FakeTesseract
) -> FakeDjvuLibre:
    """Make the document a scan: an empty text layer and two pages for OCR."""
    djvulibre.configure("djvutxt", ToolBehavior(stdout=b" \n\t"))
    djvulibre.configure("djvused", ToolBehavior(stdout=b"2\n"))
    tesseract.configure(pages=[b" one ", b" two "])
    return djvulibre


def _rejection(data: bytes = _DJVU) -> str:
    with pytest.raises(AppError) as caught:
        extract_djvu(data)
    return str(caught.value)


def _tool_calls(djvulibre: FakeDjvuLibre, tool: str) -> list[list[str]]:
    return djvulibre.arguments_of(tool)


def _with_tools(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *tools: str
) -> FakeDjvuLibre:
    fake = FakeDjvuLibre(tmp_path, tools=tools)
    monkeypatch.setenv("PATH", str(fake.bin_dir))
    return fake


@pytest.mark.usefixtures("djvulibre")
def test_returns_the_text_layer() -> None:
    text = extract_djvu(_DJVU)

    expected_text = "text layer"
    assert text == expected_text, "the text layer was not returned"


def test_runs_no_ocr_tool_when_a_text_layer_exists(djvulibre: FakeDjvuLibre) -> None:
    extract_djvu(_DJVU)

    tools = [call["tool"] for call in djvulibre.calls]
    expected_tools = ["djvutxt"]
    assert tools == expected_tools, "OCR tools ran despite a text layer"


def test_hands_the_document_to_the_tool_as_a_file(djvulibre: FakeDjvuLibre) -> None:
    extract_djvu(_DJVU)

    assert djvulibre.calls[0]["document_exists"] is True, "the document was missing"


def test_removes_the_working_directory_after_success(
    djvulibre: FakeDjvuLibre,
) -> None:
    extract_djvu(_DJVU)

    document = Path(_tool_calls(djvulibre, "djvutxt")[0][0])
    assert document.parent.exists() is False, "the working directory was left"


def test_removes_the_working_directory_after_a_failure(
    djvulibre: FakeDjvuLibre,
) -> None:
    djvulibre.configure("djvutxt", ToolBehavior(exit_code=1))
    _rejection()

    document = Path(_tool_calls(djvulibre, "djvutxt")[0][0])
    assert document.parent.exists() is False, "the working directory was left"


def test_requires_djvutxt(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _with_tools(tmp_path, monkeypatch, "djvused", "ddjvu")

    message = _rejection()

    expected = "На сервере не установлена нужная программа"
    assert message == expected, "a missing djvutxt was not reported"


def test_requires_ocr_tools_only_for_an_empty_text_layer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = _with_tools(tmp_path, monkeypatch, "djvutxt")
    fake.configure("djvutxt", ToolBehavior(stdout=b"\n"))

    message = _rejection()

    expected = "На сервере не установлена нужная программа"
    assert message == expected, "missing OCR tools were not reported"


def test_hides_djvutxt_errors_behind_a_safe_message(
    djvulibre: FakeDjvuLibre,
) -> None:
    djvulibre.configure(
        "djvutxt", ToolBehavior(exit_code=2, stderr="/srv/private/doc.djvu: bad")
    )

    message = _rejection()

    expected = "Не удалось прочитать DJVU"
    assert message == expected, "djvutxt details reached the client"


def test_replaces_invalid_utf8_in_the_text_layer(djvulibre: FakeDjvuLibre) -> None:
    djvulibre.configure("djvutxt", ToolBehavior(stdout=b"\xff\xfe" + "текст".encode()))

    text = extract_djvu(_DJVU)

    expected_text = "\N{REPLACEMENT CHARACTER}\N{REPLACEMENT CHARACTER}текст"
    assert text == expected_text, "invalid bytes were not replaced"


def test_rejects_an_oversized_text_layer(
    djvulibre: FakeDjvuLibre, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(text_layer_module, "MAX_EXTRACTED_TEXT_LENGTH", 2)
    djvulibre.configure("djvutxt", ToolBehavior(stdout=b"123456789"))

    message = _rejection()

    expected = "Текстовый слой DJVU слишком большой"
    assert message == expected, "an oversized text layer was read"


def test_stops_a_hung_djvutxt(
    djvulibre: FakeDjvuLibre, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(text_layer_module, "SUBPROCESS_TIMEOUT", 0.3)
    djvulibre.configure("djvutxt", ToolBehavior(delay=10))

    message = _rejection()

    expected = "Превышено время извлечения текста DJVU"
    assert message == expected, "a hung djvutxt was not stopped"


def test_reports_the_shared_deadline_during_djvutxt(
    djvulibre: FakeDjvuLibre,
) -> None:
    djvulibre.configure("djvutxt", ToolBehavior(delay=10))

    with pytest.raises(DeadlineExceededError) as caught:
        extract_djvu(_DJVU, deadline=Deadline(0.3))

    expected_message = "processing deadline exceeded"
    assert str(caught.value) == expected_message, "the deadline was not reported"


@pytest.mark.usefixtures("scanned")
def test_recognizes_each_page_of_a_scan() -> None:
    text = extract_djvu(_DJVU)

    expected_text = "--- Страница 1 ---\none\n\n--- Страница 2 ---\ntwo"
    assert text == expected_text, "the pages were not recognized in order"


def test_renders_each_page_at_a_bounded_size(scanned: FakeDjvuLibre) -> None:
    extract_djvu(_DJVU)

    options = [args[:3] for args in _tool_calls(scanned, "ddjvu")]
    size = f"-size={DJVU_RENDER_MAX_SIZE}x{DJVU_RENDER_MAX_SIZE}"
    expected_options = [
        ["-format=tiff", "-page=1", size],
        ["-format=tiff", "-page=2", size],
    ]
    assert options == expected_options, "pages were rendered without bounds"


@pytest.mark.parametrize(
    "output",
    [b"not-a-number", b"", b"\xff\xfe", b"1e3", b"2.5", b"0x10"],
    ids=repr,
)
def test_rejects_an_invalid_page_count(scanned: FakeDjvuLibre, output: bytes) -> None:
    scanned.configure("djvused", ToolBehavior(stdout=output))

    message = _rejection()

    expected = "Некорректное количество страниц DJVU"
    assert message == expected, "an invalid page count was accepted"


@pytest.mark.parametrize("output", [b"0", b"-3", b"  0\n"], ids=repr)
def test_rejects_a_document_without_pages(
    scanned: FakeDjvuLibre, output: bytes
) -> None:
    scanned.configure("djvused", ToolBehavior(stdout=output))

    message = _rejection()

    expected = "В DJVU не найдено страниц"
    assert message == expected, "a document without pages was accepted"


@pytest.mark.parametrize(
    "output",
    [str(MAX_DOCUMENT_PAGES + 1).encode(), b"99999999999999999999"],
    ids=repr,
)
def test_rejects_too_many_pages(scanned: FakeDjvuLibre, output: bytes) -> None:
    scanned.configure("djvused", ToolBehavior(stdout=output))

    message = _rejection()

    expected = "В DJVU слишком много страниц"
    assert message == expected, "the page limit was not applied"


def test_renders_nothing_for_too_many_pages(scanned: FakeDjvuLibre) -> None:
    scanned.configure(
        "djvused", ToolBehavior(stdout=str(MAX_DOCUMENT_PAGES + 1).encode())
    )
    _rejection()

    expected_empty: list[list[str]] = []
    assert _tool_calls(scanned, "ddjvu") == expected_empty, "a page was rendered"


def test_hides_djvused_errors_behind_a_safe_message(scanned: FakeDjvuLibre) -> None:
    scanned.configure(
        "djvused", ToolBehavior(exit_code=10, stderr="/srv/private: no such file")
    )

    message = _rejection()

    expected = "Не удалось определить количество страниц DJVU"
    assert message == expected, "djvused details reached the client"


def test_rejects_an_oversized_page_count_output(scanned: FakeDjvuLibre) -> None:
    scanned.configure("djvused", ToolBehavior(stdout=b"1" + b" " * 2048))

    message = _rejection()

    expected = "Результат программы DjVuLibre слишком большой"
    assert message == expected, "oversized djvused output was read"


def test_rejects_a_failed_render(scanned: FakeDjvuLibre) -> None:
    scanned.configure(
        "ddjvu", ToolBehavior(exit_code=1, stderr="ddjvu: cannot decode page")
    )

    message = _rejection()

    expected = "Не удалось отобразить страницу DJVU"
    assert message == expected, "a failed render was accepted"


def test_rejects_a_render_that_writes_no_image(scanned: FakeDjvuLibre) -> None:
    scanned.configure("ddjvu", ToolBehavior())

    message = _rejection()

    expected = "Не удалось отобразить страницу DJVU"
    assert message == expected, "a missing rendered page was accepted"


def test_rejects_an_oversized_rendered_page(
    scanned: FakeDjvuLibre, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(ocr_pages_module, "MAX_DJVU_PAGE_BYTES", 3)
    scanned.configure("ddjvu", ToolBehavior(page=b"four"))

    message = _rejection()

    expected = "Страница DJVU слишком велика для OCR"
    assert message == expected, "an oversized rendered page was accepted"


@pytest.mark.usefixtures("scanned")
def test_does_not_recognize_an_oversized_rendered_page(
    tesseract: FakeTesseract, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(ocr_pages_module, "MAX_DJVU_PAGE_BYTES", 3)
    _rejection()

    expected_empty: list[list[str]] = []
    assert tesseract.recognitions == expected_empty, "an oversized page reached OCR"


def test_stops_a_hung_render(
    scanned: FakeDjvuLibre, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(ocr_pages_module, "SUBPROCESS_TIMEOUT", 0.3)
    scanned.configure("ddjvu", ToolBehavior(delay=10))

    message = _rejection()

    expected = "Превышено время обработки DJVU"
    assert message == expected, "a hung ddjvu was not stopped"


def _ocr_into(pages: Path, scanned: FakeDjvuLibre) -> str:
    document = pages.parent / "scan.djvu"
    document.write_bytes(_DJVU)
    return extract_ocr_pages(
        document,
        pages,
        str(scanned.bin_dir / "djvused"),
        str(scanned.bin_dir / "ddjvu"),
    )


def test_removes_rendered_pages_after_recognition(
    scanned: FakeDjvuLibre, tmp_path: Path
) -> None:
    pages = tmp_path / "pages"
    pages.mkdir()
    _ocr_into(pages, scanned)

    expected_empty: list[str] = []
    leftovers = [path.name for path in pages.iterdir()]
    assert leftovers == expected_empty, "a rendered page was left on disk"


def test_removes_a_rendered_page_when_recognition_fails(
    scanned: FakeDjvuLibre, tesseract: FakeTesseract, tmp_path: Path
) -> None:
    tesseract.configure(exit_code=1)
    pages = tmp_path / "pages"
    pages.mkdir()
    with pytest.raises(AppError):
        _ocr_into(pages, scanned)

    expected_empty: list[str] = []
    leftovers = [path.name for path in pages.iterdir()]
    assert leftovers == expected_empty, "a failed page was left on disk"


def _exact_fit_context(
    scanned: FakeDjvuLibre, tesseract: FakeTesseract, pages: int
) -> ExtractContext:
    scanned.configure("djvused", ToolBehavior(stdout=str(pages).encode()))
    page_text = "Скан №5"
    tesseract.configure(pages=[page_text.encode()])
    budget = TextBudget(len(f"--- Страница 1 ---\n{page_text}"))
    return ExtractContext(budget=budget, deadline=Deadline(30))


def test_stops_at_an_exact_fit_when_more_pages_follow(
    scanned: FakeDjvuLibre, tesseract: FakeTesseract
) -> None:
    context = _exact_fit_context(scanned, tesseract, 2)

    text = extract_djvu(_DJVU, context=context)

    expected_text = "--- Страница 1 ---\nСкан №5"
    assert text == expected_text, "text beyond the budget was returned"


def test_marks_truncation_when_pages_remain_after_an_exact_fit(
    scanned: FakeDjvuLibre, tesseract: FakeTesseract
) -> None:
    context = _exact_fit_context(scanned, tesseract, 2)

    extract_djvu(_DJVU, context=context)

    assert context.budget.truncated is True, "the omitted page was not reported"


def test_renders_no_page_after_an_exact_fit(
    scanned: FakeDjvuLibre, tesseract: FakeTesseract
) -> None:
    context = _exact_fit_context(scanned, tesseract, 2)

    extract_djvu(_DJVU, context=context)

    expected_renders = 1
    assert len(_tool_calls(scanned, "ddjvu")) == expected_renders, "probed a page"


def test_exact_fit_on_the_last_page_is_not_truncated(
    scanned: FakeDjvuLibre, tesseract: FakeTesseract
) -> None:
    context = _exact_fit_context(scanned, tesseract, 1)

    extract_djvu(_DJVU, context=context)

    assert context.budget.truncated is False, "a complete document was truncated"
