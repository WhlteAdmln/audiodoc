"""Unit tests for bounded DJVU text extraction and page rendering."""

from pathlib import Path
from types import SimpleNamespace

import pytest

import backend.document_engine.extractors.djvu as djvu_module
import backend.document_engine.extractors.djvu.ocr_pages as ocr_pages_module
import backend.document_engine.extractors.djvu.text_layer as text_layer_module
from backend.document_engine.extractors.djvu.ocr_pages import extract_ocr_pages
from backend.document_engine.extractors.djvu.text_layer import extract_text_layer
from backend.document_engine.extractors.djvu.tools import DjvuTools
from backend.document_engine.limits import (
    DJVU_RENDER_MAX_SIZE,
    MAX_DOCUMENT_PAGES,
    MAX_DJVU_PAGE_BYTES,
    SUBPROCESS_TIMEOUT,
)
from backend.common.subprocess_runner import SubprocessTimeoutError
from backend.errors.documents import (
    DependencyMissingError,
    DocumentRejectedError,
    ProcessingTimeoutError,
)


def test_djvu_returns_text_layer_without_running_ocr(monkeypatch):
    captured = {}
    tools = DjvuTools("/usr/bin/djvutxt", None, None)
    monkeypatch.setattr(djvu_module, "find_djvu_tools", lambda: tools)

    def fake_extract_text_layer(file_path: Path, executable: str, *, context=None):
        captured["file_path"] = file_path
        captured["executable"] = executable
        assert file_path.read_bytes() == b"DJVU-data"
        return "Text layer content"

    def unexpected_ocr(*_args, **_kwargs):
        raise AssertionError("OCR must not run when a text layer exists")

    monkeypatch.setattr(djvu_module, "extract_text_layer", fake_extract_text_layer)
    monkeypatch.setattr(djvu_module, "extract_ocr_pages", unexpected_ocr)
    assert djvu_module.extract_djvu(b"DJVU-data") == "Text layer content"
    assert captured["executable"] == "/usr/bin/djvutxt"
    assert not captured["file_path"].parent.exists()


def test_djvu_uses_ocr_when_text_layer_is_empty(monkeypatch):
    tools = DjvuTools("/usr/bin/djvutxt", "/usr/bin/djvused", "/usr/bin/ddjvu")
    captured = {}
    monkeypatch.setattr(djvu_module, "find_djvu_tools", lambda: tools)
    monkeypatch.setattr(djvu_module, "extract_text_layer", lambda *_args, **_kwargs: "")

    def fake_extract_ocr_pages(file_path, temp_path, djvused, ddjvu, *, context=None):
        captured.update(
            file_path=file_path, temp_path=temp_path, djvused=djvused, ddjvu=ddjvu
        )
        assert file_path.read_bytes() == b"DJVU-data"
        return "OCR result"

    monkeypatch.setattr(djvu_module, "extract_ocr_pages", fake_extract_ocr_pages)
    assert djvu_module.extract_djvu(b"DJVU-data") == "OCR result"
    assert captured["djvused"] == "/usr/bin/djvused"
    assert captured["ddjvu"] == "/usr/bin/ddjvu"
    assert not captured["temp_path"].exists()


def test_djvu_requires_djvutxt(monkeypatch):
    monkeypatch.setattr(
        djvu_module,
        "find_djvu_tools",
        lambda: DjvuTools(None, "/usr/bin/djvused", "/usr/bin/ddjvu"),
    )
    with pytest.raises(DependencyMissingError):
        djvu_module.extract_djvu(b"DJVU-data")


def test_djvu_requires_ocr_tools_only_when_text_layer_is_empty(monkeypatch):
    monkeypatch.setattr(
        djvu_module,
        "find_djvu_tools",
        lambda: DjvuTools("/usr/bin/djvutxt", None, None),
    )
    monkeypatch.setattr(djvu_module, "extract_text_layer", lambda *_args, **_kwargs: "")
    with pytest.raises(DependencyMissingError):
        djvu_module.extract_djvu(b"DJVU-data")


def test_text_layer_maps_subprocess_timeout_to_processing_timeout(monkeypatch):
    def timeout(*_args, **_kwargs):
        raise SubprocessTimeoutError("timeout")

    monkeypatch.setattr(text_layer_module, "run_limited", timeout)
    with pytest.raises(ProcessingTimeoutError):
        extract_text_layer(Path("document.djvu"), "/usr/bin/djvutxt")


def test_text_layer_uses_bounded_output_and_hides_stderr(monkeypatch, tmp_path):
    captured = {}

    def fake_run(args, *, timeout, max_output):
        captured.update(args=args, timeout=timeout, max_output=max_output)
        return 1, b"", b"DJVU parser error /private/tmp/file"

    monkeypatch.setattr(text_layer_module, "run_limited", fake_run)
    with pytest.raises(DocumentRejectedError, match="Не удалось прочитать DJVU"):
        extract_text_layer(tmp_path / "document.djvu", "/usr/bin/djvutxt")
    assert captured["max_output"] > 0
    assert captured["timeout"] == SUBPROCESS_TIMEOUT


def test_ocr_pages_renders_at_bounded_size_and_recognizes_each_page(
    monkeypatch, tmp_path
):
    document_path = tmp_path / "document.djvu"
    document_path.write_bytes(b"DJVU-data")
    calls = []

    def fake_run(args, *, timeout, max_output):
        calls.append((args, timeout, max_output))
        if args[0] == "/usr/bin/djvused":
            return 0, b"2", b""
        if args[0] == "/usr/bin/ddjvu":
            Path(args[-1]).write_bytes(b"TIFF-data")
            return 0, b"", b""
        raise AssertionError(f"Unexpected command: {args[0]}")

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

    assert text == "--- Страница 1 ---\nPage one\n\n--- Страница 2 ---\nPage two"
    assert [call[1] for call in calls] == [SUBPROCESS_TIMEOUT] * 3
    assert all(call[2] <= 4096 for call in calls)
    render_args = calls[1][0]
    assert f"-size={DJVU_RENDER_MAX_SIZE}x{DJVU_RENDER_MAX_SIZE}" in render_args
    assert not (tmp_path / "page_1.tiff").exists()
    assert not (tmp_path / "page_2.tiff").exists()


def test_ocr_pages_rejects_too_many_pages(monkeypatch, tmp_path):
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


def test_ocr_pages_rejects_too_large_rendered_file(monkeypatch, tmp_path):
    document_path = tmp_path / "document.djvu"
    document_path.write_bytes(b"DJVU-data")
    monkeypatch.setattr(ocr_pages_module, "MAX_DJVU_PAGE_BYTES", 3)

    def fake_run(args, **_kwargs):
        if args[0] == "/usr/bin/djvused":
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
