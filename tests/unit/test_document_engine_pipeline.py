"""Проверки реестра, синхронного pipeline и публичных импортов."""

import asyncio
import threading
from pathlib import Path

import pytest

from backend.document_engine import (
    pipeline,
    process_document_sync,
    runner,
)
from backend.document_engine.extractors import REGISTRY, _odf
from backend.errors.documents import DocumentRejectedError, UnsupportedFormatError

EXPECTED_FORMATS = {
    "pdf",
    "docx",
    "xlsx",
    "pptx",
    "epub",
    "fb2",
    "djvu",
    "odt",
    "ods",
    "odp",
    "txt",
    "md",
    "csv",
    "html",
    "xml",
    "rtf",
}


def test_registry_contains_all_supported_document_formats():
    assert set(REGISTRY) == EXPECTED_FORMATS
    assert REGISTRY["txt"] is REGISTRY["md"]


def test_odf_registry_entries_dispatch_to_the_correct_type(monkeypatch):
    calls = []

    def fake_extract_odf(data, filetype, *, context=None, deadline=None):
        calls.append((data, filetype))
        return filetype.upper()

    monkeypatch.setattr(
        "backend.document_engine.extractors.extract_odf",
        fake_extract_odf,
    )

    # ODF adapters resolve the shared extract_odf function at call time.
    # Rebuild only the three entries to make their dispatch observable.
    for kind in ("odt", "ods", "odp"):
        assert _odf(kind)(b"odf") == kind.upper()

    assert calls == [(b"odf", "odt"), (b"odf", "ods"), (b"odf", "odp")]


def test_pipeline_dispatches_registered_extractor_and_builds_result(monkeypatch):
    monkeypatch.setattr(pipeline, "detect_format", lambda _data, _name: "txt")
    monkeypatch.setitem(
        pipeline.REGISTRY,
        "txt",
        lambda _data, *, context=None: "  extracted text  ",
    )

    assert pipeline.process_document_sync(b"payload", "note.txt") == {
        "format": "txt",
        "text": "extracted text",
        "characters": 14,
        "truncated": False,
    }


def test_pipeline_validates_zip_before_calling_extractor(monkeypatch):
    events = []
    monkeypatch.setattr(pipeline, "detect_format", lambda _data, _name: "docx")
    monkeypatch.setattr(
        pipeline,
        "validate_zip_archive",
        lambda _data: events.append("validated"),
    )
    monkeypatch.setitem(
        pipeline.REGISTRY,
        "docx",
        lambda _data, *, context=None: events.append("extracted") or "word",
    )

    result = pipeline.process_document_sync(b"zip payload", "note.docx")

    assert events == ["validated", "extracted"]
    assert result["format"] == "docx"
    assert result["text"] == "word"
    assert result["truncated"] is False


def test_pipeline_preserves_safe_empty_and_unsupported_document_errors(monkeypatch):
    with pytest.raises(DocumentRejectedError, match="Документ пуст"):
        process_document_sync(b"", "empty.txt")

    monkeypatch.setattr(pipeline, "detect_format", lambda _data, _name: None)
    with pytest.raises(UnsupportedFormatError):
        process_document_sync(b"image", "image.png")


def test_legacy_processor_shim_has_been_removed():
    processor_path = (
        Path(__file__).parents[2] / "backend" / "document_engine" / "processor.py"
    )
    assert not processor_path.exists()


def test_async_runner_executes_sync_pipeline_in_a_worker_thread(monkeypatch):
    main_thread = threading.get_ident()
    calls = []

    def fake_process(data, filename, max_characters, deadline):
        calls.append((data, filename, max_characters, deadline, threading.get_ident()))
        return {"format": "txt", "text": "ok", "characters": 2, "truncated": False}

    monkeypatch.setattr(runner, "process_document_sync", fake_process)

    result = asyncio.run(runner.process_document(b"body", "note.txt"))

    assert result == {
        "format": "txt",
        "text": "ok",
        "characters": 2,
        "truncated": False,
    }
    assert calls[0][:3] == (b"body", "note.txt", None)
    assert calls[0][3] is not None
    assert calls[0][4] != main_thread


def test_pipeline_applies_client_character_hint_and_marks_truncation():
    result = process_document_sync(b"0123456789", "note.txt", max_characters=5)
    assert result == {
        "format": "txt",
        "text": "01234",
        "characters": 5,
        "truncated": True,
    }


def test_pipeline_exact_budget_is_not_truncated():
    result = process_document_sync(b"12345", "note.txt", max_characters=5)

    assert result == {
        "format": "txt",
        "text": "12345",
        "characters": 5,
        "truncated": False,
    }


def test_pipeline_truncates_one_character_over_budget():
    result = process_document_sync(b"123456", "note.txt", max_characters=5)

    assert result == {
        "format": "txt",
        "text": "12345",
        "characters": 5,
        "truncated": True,
    }


def test_pipeline_rejects_invalid_character_hint():
    with pytest.raises(DocumentRejectedError, match="лимит длины текста"):
        process_document_sync(b"hello", "note.txt", max_characters=0)


def test_pipeline_hides_unexpected_extractor_exception(monkeypatch, caplog):
    monkeypatch.setattr(pipeline, "detect_format", lambda _data, _name: "txt")

    def fail_extractor(_data, *, context=None):
        raise RuntimeError("/private/path/to/parser-internal-error")

    monkeypatch.setitem(pipeline.REGISTRY, "txt", fail_extractor)

    with pytest.raises(DocumentRejectedError) as error:
        process_document_sync(b"payload", "note.txt")

    assert error.value.public_message == (
        "\u041d\u0435 удалось прочитать документ: файл повреждён или имеет "
        "неподдерживаемую структуру"
    )
    assert "/private/path/to/parser-internal-error" not in error.value.public_message
