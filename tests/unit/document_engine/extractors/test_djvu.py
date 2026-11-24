# Copyright (c) 2026 Nikolai Zelensky
"""Unit tests for bounded DJVU text extraction and page rendering."""

from pathlib import Path
from typing import Never

import pytest

import audiodoc.document_engine.extractors.djvu as djvu_module
import audiodoc.document_engine.extractors.djvu.ocr_pages as ocr_pages_module
import audiodoc.document_engine.extractors.djvu.text_layer as text_layer_module
from audiodoc.common.deadline import Deadline
from audiodoc.common.subprocess_runner import (
    SubprocessOutputLimitError,
    SubprocessTimeoutError,
)
from audiodoc.common.text_budget import TextBudget
from audiodoc.document_engine.extractors.base import ExtractContext
from audiodoc.document_engine.extractors.djvu.ocr_pages import extract_ocr_pages
from audiodoc.document_engine.extractors.djvu.text_layer import extract_text_layer
from audiodoc.document_engine.extractors.djvu.tools import DjvuTools
from audiodoc.document_engine.limits import (
    DJVU_RENDER_MAX_SIZE,
    MAX_DOCUMENT_PAGES,
    SUBPROCESS_TIMEOUT,
)
from audiodoc.errors.documents import (
    DependencyMissingError,
    DocumentRejectedError,
    ProcessingTimeoutError,
)


class _UnexpectedDjvuCommandError(AssertionError):
    """Raised when the test receives an unexpected DjVu command."""

    def __init__(self, command: str) -> None:
        """Initialize the assertion error with the unexpected command."""
        super().__init__(f"Unexpected command: {command}")


class _UnexpectedOcrCallError(AssertionError):
    """Raised when OCR is unexpectedly called despite an existing text layer."""

    def __init__(self) -> None:
        """Initialize the test assertion error."""
        super().__init__("OCR must not run when a text layer exists")


def test_djvu_returns_text_layer_without_running_ocr(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = {}
    tools = DjvuTools("/usr/bin/djvutxt", None, None)
    monkeypatch.setattr(djvu_module, "find_djvu_tools", lambda: tools)

    def fake_extract_text_layer(
        file_path: Path, executable: str, **_kwargs: object
    ) -> str:
        captured["file_path"] = file_path
        captured["executable"] = executable
        expected_read_bytes = b"DJVU-data"
        assert file_path.read_bytes() == expected_read_bytes
        return "Text layer content"

    def unexpected_ocr(*_args: object, **_kwargs: object) -> Never:
        raise _UnexpectedOcrCallError

    monkeypatch.setattr(djvu_module, "extract_text_layer", fake_extract_text_layer)
    monkeypatch.setattr(djvu_module, "extract_ocr_pages", unexpected_ocr)
    expected_extract_djvu = "Text layer content"
    assert djvu_module.extract_djvu(b"DJVU-data") == expected_extract_djvu
    expected_executable = "/usr/bin/djvutxt"
    assert captured["executable"] == expected_executable
    assert not captured["file_path"].parent.exists()


def test_djvu_uses_ocr_when_text_layer_is_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tools = DjvuTools("/usr/bin/djvutxt", "/usr/bin/djvused", "/usr/bin/ddjvu")
    captured = {}
    monkeypatch.setattr(djvu_module, "find_djvu_tools", lambda: tools)
    monkeypatch.setattr(djvu_module, "extract_text_layer", lambda *_args, **_kwargs: "")

    def fake_extract_ocr_pages(
        file_path: object,
        temp_path: object,
        djvused: object,
        ddjvu: object,
        **_kwargs: object,
    ) -> str:
        captured.update(
            file_path=file_path, temp_path=temp_path, djvused=djvused, ddjvu=ddjvu
        )
        expected_read_bytes = b"DJVU-data"
        assert file_path.read_bytes() == expected_read_bytes
        return "OCR result"

    monkeypatch.setattr(djvu_module, "extract_ocr_pages", fake_extract_ocr_pages)
    expected_extract_djvu = "OCR result"
    assert djvu_module.extract_djvu(b"DJVU-data") == expected_extract_djvu
    expected_djvused = "/usr/bin/djvused"
    assert captured["djvused"] == expected_djvused
    expected_ddjvu = "/usr/bin/ddjvu"
    assert captured["ddjvu"] == expected_ddjvu
    assert not captured["temp_path"].exists()


def test_djvu_requires_djvutxt(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        djvu_module,
        "find_djvu_tools",
        lambda: DjvuTools(None, "/usr/bin/djvused", "/usr/bin/ddjvu"),
    )
    with pytest.raises(DependencyMissingError):
        djvu_module.extract_djvu(b"DJVU-data")


def test_djvu_requires_ocr_tools_only_when_text_layer_is_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        djvu_module,
        "find_djvu_tools",
        lambda: DjvuTools("/usr/bin/djvutxt", None, None),
    )
    monkeypatch.setattr(djvu_module, "extract_text_layer", lambda *_args, **_kwargs: "")
    with pytest.raises(DependencyMissingError):
        djvu_module.extract_djvu(b"DJVU-data")


def test_text_layer_maps_subprocess_timeout_to_processing_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def timeout(*_args: object, **_kwargs: object) -> Never:
        timeout_message = "timeout"
        raise SubprocessTimeoutError(timeout_message)

    monkeypatch.setattr(text_layer_module, "run_limited", timeout)
    with pytest.raises(ProcessingTimeoutError):
        extract_text_layer(Path("document.djvu"), "/usr/bin/djvutxt")


def test_text_layer_uses_bounded_output_and_hides_stderr(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    captured = {}

    def fake_run(args: object, *, timeout: object, max_output: object) -> object:
        captured.update(args=args, timeout=timeout, max_output=max_output)
        return 1, b"", b"DJVU parser error /private/tmp/file"

    monkeypatch.setattr(text_layer_module, "run_limited", fake_run)
    with pytest.raises(
        DocumentRejectedError,
        match="\u041d\u0435 удалось прочитать DJVU",
    ):
        extract_text_layer(tmp_path / "document.djvu", "/usr/bin/djvutxt")
    assert captured["max_output"] > 0
    assert captured["timeout"] == SUBPROCESS_TIMEOUT


def test_ocr_pages_renders_at_bounded_size_and_recognizes_each_page(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    document_path = tmp_path / "document.djvu"
    document_path.write_bytes(b"DJVU-data")
    calls = []

    def fake_run(args: object, *, timeout: object, max_output: object) -> object:
        calls.append((args, timeout, max_output))
        djvused_path = "/usr/bin/djvused"
        if args[0] == djvused_path:
            return 0, b"2", b""
        ddjvu_path = "/usr/bin/ddjvu"
        if args[0] == ddjvu_path:
            Path(args[-1]).write_bytes(b"TIFF-data")
            return 0, b"", b""
        raise _UnexpectedDjvuCommandError(args[0])

    recognized = iter((" Page one ", " Page two "))
    monkeypatch.setattr(ocr_pages_module, "run_limited", fake_run)
    monkeypatch.setattr(
        ocr_pages_module,
        "extract_image_text",
        lambda _data, **_kwargs: next(recognized),
    )

    text = extract_ocr_pages(
        document_path,
        tmp_path,
        "/usr/bin/djvused",
        "/usr/bin/ddjvu",
    )

    expected_text = "--- Страница 1 ---\nPage one\n\n--- Страница 2 ---\nPage two"
    assert text == expected_text
    assert [call[1] for call in calls] == [SUBPROCESS_TIMEOUT] * 3
    expected_call = 4096
    assert all(call[2] <= expected_call for call in calls)
    render_args = calls[1][0]
    assert f"-size={DJVU_RENDER_MAX_SIZE}x{DJVU_RENDER_MAX_SIZE}" in render_args
    assert not (tmp_path / "page_1.tiff").exists()
    assert not (tmp_path / "page_2.tiff").exists()


def test_ocr_pages_rejects_too_many_pages(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    document_path = tmp_path / "document.djvu"
    document_path.write_bytes(b"DJVU-data")
    monkeypatch.setattr(
        ocr_pages_module,
        "run_limited",
        lambda *_args, **_kwargs: (0, str(MAX_DOCUMENT_PAGES + 1).encode("ascii"), b""),
    )
    with pytest.raises(DocumentRejectedError):
        extract_ocr_pages(
            document_path,
            tmp_path,
            "/usr/bin/djvused",
            "/usr/bin/ddjvu",
        )


def test_ocr_pages_rejects_too_large_rendered_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    document_path = tmp_path / "document.djvu"
    document_path.write_bytes(b"DJVU-data")
    monkeypatch.setattr(ocr_pages_module, "MAX_DJVU_PAGE_BYTES", 3)

    def fake_run(args: object, **_kwargs: object) -> object:
        expected_args = "/usr/bin/djvused"
        if args[0] == expected_args:
            return 0, b"1", b""
        Path(args[-1]).write_bytes(b"four")
        return 0, b"", b""

    monkeypatch.setattr(ocr_pages_module, "run_limited", fake_run)
    monkeypatch.setattr(
        ocr_pages_module,
        "extract_image_text",
        lambda *_args, **_kwargs: pytest.fail("oversized TIFF must not be read by OCR"),
    )
    with pytest.raises(DocumentRejectedError, match="слишком велика"):
        extract_ocr_pages(
            document_path,
            tmp_path,
            "/usr/bin/djvused",
            "/usr/bin/ddjvu",
        )


def test_ocr_pages_marks_remaining_pages_as_truncated_after_exact_fit(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    document_path = tmp_path / "document.djvu"
    document_path.write_bytes(b"DJVU-data")
    calls = []

    def fake_run(args: object, **_kwargs: object) -> object:
        calls.append(args)
        expected_args = "/usr/bin/djvused"
        if args[0] == expected_args:
            return 0, b"2", b""
        Path(args[-1]).write_bytes(b"TIFF-data")
        return 0, b"", b""

    monkeypatch.setattr(ocr_pages_module, "run_limited", fake_run)
    monkeypatch.setattr(
        ocr_pages_module, "extract_image_text", lambda *_args, **_kwargs: "abc"
    )
    page_text = "--- Страница 1 ---\nabc"
    budget = TextBudget(len(page_text))
    context = ExtractContext(budget=budget, deadline=Deadline(10))

    assert (
        extract_ocr_pages(
            document_path,
            tmp_path,
            "/usr/bin/djvused",
            "/usr/bin/ddjvu",
            context=context,
        )
        == page_text
    )
    assert budget.truncated is True
    expected_subprocess_calls = 2
    assert len(calls) == expected_subprocess_calls, "page two must not be rendered"


def test_ocr_pages_exact_fit_on_last_page_is_not_truncated(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    document_path = tmp_path / "document.djvu"
    document_path.write_bytes(b"DJVU-data")

    def fake_run(args: object, **_kwargs: object) -> object:
        expected_args = "/usr/bin/djvused"
        if args[0] == expected_args:
            return 0, b"1", b""
        Path(args[-1]).write_bytes(b"TIFF-data")
        return 0, b"", b""

    monkeypatch.setattr(ocr_pages_module, "run_limited", fake_run)
    monkeypatch.setattr(
        ocr_pages_module, "extract_image_text", lambda *_args, **_kwargs: "abc"
    )
    page_text = "--- Страница 1 ---\nabc"
    budget = TextBudget(len(page_text))
    context = ExtractContext(budget=budget, deadline=Deadline(10))

    assert (
        extract_ocr_pages(
            document_path,
            tmp_path,
            "/usr/bin/djvused",
            "/usr/bin/ddjvu",
            context=context,
        )
        == page_text
    )
    assert budget.truncated is False


def test_text_layer_maps_subprocess_output_limit(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def output_limit(*_args: object, **_kwargs: object) -> Never:
        message = "output limit"
        raise SubprocessOutputLimitError(message)

    monkeypatch.setattr(text_layer_module, "run_limited", output_limit)
    with pytest.raises(DocumentRejectedError):
        extract_text_layer(tmp_path / "document.djvu", "/usr/bin/djvutxt")


@pytest.mark.parametrize(
    ("return_code", "output"),
    [(1, b"1"), (0, b"not-a-number"), (0, b"0")],
)
def test_ocr_pages_rejects_invalid_page_count(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    return_code: object,
    output: object,
) -> None:
    monkeypatch.setattr(
        ocr_pages_module,
        "run_limited",
        lambda *_args, **_kwargs: (return_code, output, b"private details"),
    )
    with pytest.raises(DocumentRejectedError):
        extract_ocr_pages(
            tmp_path / "document.djvu",
            tmp_path,
            "/usr/bin/djvused",
            "/usr/bin/ddjvu",
        )


@pytest.mark.parametrize("return_code", [0, 1])
def test_ocr_pages_rejects_failed_or_missing_render(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    return_code: int,
) -> None:
    def fake_run(args: object, **_kwargs: object) -> object:
        expected_args = "/usr/bin/djvused"
        if args[0] == expected_args:
            return 0, b"1", b""
        return return_code, b"", b"private details"

    monkeypatch.setattr(ocr_pages_module, "run_limited", fake_run)
    with pytest.raises(DocumentRejectedError):
        extract_ocr_pages(
            tmp_path / "document.djvu",
            tmp_path,
            "/usr/bin/djvused",
            "/usr/bin/ddjvu",
        )


@pytest.mark.parametrize(
    ("error_type", "expected_error"),
    [
        (SubprocessOutputLimitError, DocumentRejectedError),
        (SubprocessTimeoutError, ProcessingTimeoutError),
    ],
)
def test_ocr_pages_maps_subprocess_failures(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    error_type: object,
    expected_error: object,
) -> None:
    def fail(*_args: object, **_kwargs: object) -> Never:
        message = "subprocess failure"
        raise error_type(message)

    monkeypatch.setattr(ocr_pages_module, "run_limited", fail)
    with pytest.raises(expected_error):
        extract_ocr_pages(
            tmp_path / "document.djvu",
            tmp_path,
            "/usr/bin/djvused",
            "/usr/bin/ddjvu",
        )
