# Copyright (c) 2026 Nikolai Zelensky
"""Tests for the doctor command."""

import pytest

from audiodoc import cli
from audiodoc.cli import doctor as doctor_command
from audiodoc.system_diagnostics import DiagnosticCheck


def test_doctor_prints_checks_and_warnings_do_not_fail(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    calls: list[str] = []
    monkeypatch.setattr(doctor_command, "load_env_file", lambda: calls.append("env"))
    monkeypatch.setattr(
        doctor_command,
        "collect_doctor_checks",
        lambda _environ: (
            DiagnosticCheck("Python", "OK", "Python 3.11 is supported."),
            DiagnosticCheck("Bind address", "WARN", "Binding to all interfaces."),
        ),
    )

    assert cli.main(["doctor"]) == 0
    assert calls == ["env"]
    assert capsys.readouterr().out.splitlines() == [
        "OK   Python: Python 3.11 is supported.",
        "WARN Bind address: Binding to all interfaces.",
    ]


def test_doctor_fails_and_prints_native_tool_install_commands(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(doctor_command, "load_env_file", lambda: None)
    monkeypatch.setattr(
        doctor_command,
        "collect_doctor_checks",
        lambda _environ: (
            DiagnosticCheck("Tesseract", "FAIL", "Executable not found."),
            DiagnosticCheck("DjVuLibre", "FAIL", "Executables not found."),
        ),
    )

    assert cli.main(["doctor"]) == 1
    output = capsys.readouterr().out

    expected_fragment = "FAIL Tesseract: Executable not found."
    assert expected_fragment in output
    expected_fragment = "FAIL DjVuLibre: Executables not found."
    assert expected_fragment in output
    expected_fragment_2 = (
        "sudo apt install tesseract-ocr tesseract-ocr-rus "
        "tesseract-ocr-eng djvulibre-bin"
    )
    assert expected_fragment_2 in output
    expected_fragment_2 = (
        "sudo dnf install tesseract tesseract-langpack-rus "
        "tesseract-langpack-eng djvulibre"
    )
    assert expected_fragment_2 in output
    expected_fragment = (
        "sudo pacman -S tesseract tesseract-data-rus tesseract-data-eng djvulibre"
    )
    assert expected_fragment in output
