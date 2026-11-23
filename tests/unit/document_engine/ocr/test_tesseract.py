# Copyright (c) 2026 Nikolai Zelensky

"""Tests for ocr tesseract."""

import pytest

import audiodoc.document_engine.ocr.tesseract as tesseract_module
from audiodoc.document_engine.ocr import tesseract as ocr_tesseract
from audiodoc.errors.documents import DependencyMissingError


def test_check_tesseract_requires_binary_when_not_installed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(ocr_tesseract.shutil, "which", lambda _: None)
    with pytest.raises(DependencyMissingError):
        ocr_tesseract._check_tesseract()


def test_check_languages_reports_missing_language(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        ocr_tesseract.pytesseract,
        "get_languages",
        lambda *_args, **_kwargs: ["eng"],
    )
    with pytest.raises(DependencyMissingError):
        ocr_tesseract._check_languages("rus+eng")


def test_tesseract_language_checks_are_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"binary": 0, "languages": 0}
    tesseract_module.ensure_ready.cache_clear()

    def check_binary() -> None:
        calls["binary"] += 1

    def check_languages(_languages: object) -> None:
        calls["languages"] += 1

    monkeypatch.setattr(tesseract_module, "_check_tesseract", check_binary)
    monkeypatch.setattr(tesseract_module, "_check_languages", check_languages)

    for _ in range(5):
        tesseract_module.ensure_ready("rus+eng")

    assert calls == {"binary": 1, "languages": 1}
    tesseract_module.ensure_ready.cache_clear()
