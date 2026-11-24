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

    tesseract_failure = "FAIL Tesseract: Executable not found."
    assert tesseract_failure in output
    djvulibre_failure = "FAIL DjVuLibre: Executables not found."
    assert djvulibre_failure in output
    apt_command = (
        "sudo apt install tesseract-ocr tesseract-ocr-rus "
        "tesseract-ocr-eng djvulibre-bin"
    )
    assert apt_command in output
    dnf_command = (
        "sudo dnf install tesseract tesseract-langpack-rus "
        "tesseract-langpack-eng djvulibre"
    )
    assert dnf_command in output
    pacman_command = (
        "sudo pacman -S tesseract tesseract-data-rus tesseract-data-eng djvulibre"
    )
    assert pacman_command in output
