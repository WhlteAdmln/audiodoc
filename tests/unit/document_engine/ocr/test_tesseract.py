# Copyright (c) 2026 Nikolai Zelensky

"""Tests for ocr tesseract."""

import pytest

import audiodoc.document_engine.ocr.tesseract as tesseract_module
from audiodoc.errors.documents import DependencyMissingError


def test_ensure_ready_requires_binary_when_not_installed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tesseract_module.ensure_ready.cache_clear()
    monkeypatch.setattr(tesseract_module.shutil, "which", lambda _: None)
    with pytest.raises(DependencyMissingError):
        tesseract_module.ensure_ready("rus+eng")


def test_ensure_ready_reports_missing_language(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tesseract_module.ensure_ready.cache_clear()
    monkeypatch.setattr(
        tesseract_module.shutil, "which", lambda _: "/opt/bin/tesseract"
    )
    monkeypatch.setattr(
        tesseract_module.pytesseract,
        "get_languages",
        lambda *_args, **_kwargs: ["eng"],
    )
    with pytest.raises(DependencyMissingError):
        tesseract_module.ensure_ready("rus+eng")


def test_ensure_ready_reports_unreadable_language_list(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tesseract_module.ensure_ready.cache_clear()
    monkeypatch.setattr(
        tesseract_module.shutil, "which", lambda _: "/opt/bin/tesseract"
    )

    def broken_languages(*_args: object, **_kwargs: object) -> list[str]:
        message = "tessdata directory is unreadable"
        raise OSError(message)

    monkeypatch.setattr(tesseract_module.pytesseract, "get_languages", broken_languages)
    with pytest.raises(DependencyMissingError):
        tesseract_module.ensure_ready("deu+fra")


def test_ensure_ready_checks_each_language_expression_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tesseract_module.ensure_ready.cache_clear()
    calls = {"binary": 0, "languages": 0}

    def which(_name: str) -> str:
        calls["binary"] += 1
        return "/opt/bin/tesseract"

    def get_languages(*_args: object, **_kwargs: object) -> list[str]:
        calls["languages"] += 1
        return ["eng", "rus"]

    monkeypatch.setattr(tesseract_module.shutil, "which", which)
    monkeypatch.setattr(tesseract_module.pytesseract, "get_languages", get_languages)

    for _ in range(5):
        tesseract_module.ensure_ready("rus+eng")

    expected_calls = {"binary": 1, "languages": 1}
    assert calls == expected_calls, "ensure_ready repeated a cached startup check"
