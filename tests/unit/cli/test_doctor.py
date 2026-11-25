# Copyright (c) 2026 Nikolai Zelensky
"""Tests for the doctor command."""

import pytest

from audiodoc import cli
from audiodoc.cli import doctor as doctor_command
from audiodoc.system_diagnostics import DiagnosticCheck


@pytest.fixture(name="env_loads")
def fixture_env_loads(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Record environment file loads and report one passing and one warning check."""
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
    return calls


@pytest.fixture(name="failing_checks")
def fixture_failing_checks(monkeypatch: pytest.MonkeyPatch) -> None:
    """Report failing native tool checks to the doctor command."""
    monkeypatch.setattr(doctor_command, "load_env_file", lambda: None)
    monkeypatch.setattr(
        doctor_command,
        "collect_doctor_checks",
        lambda _environ: (
            DiagnosticCheck("Tesseract", "FAIL", "Executable not found."),
            DiagnosticCheck("DjVuLibre", "FAIL", "Executables not found."),
        ),
    )


@pytest.mark.usefixtures("env_loads")
def test_doctor_warnings_do_not_fail() -> None:
    exit_code = cli.main(["doctor"])

    expected_exit_code = 0
    assert exit_code == expected_exit_code, "warnings failed the doctor command"


def test_doctor_loads_the_env_file(env_loads: list[str]) -> None:
    cli.main(["doctor"])

    expected_loads = ["env"]
    assert env_loads == expected_loads, "the doctor command did not load the env file"


@pytest.mark.usefixtures("env_loads")
def test_doctor_prints_checks(capsys: pytest.CaptureFixture[str]) -> None:
    cli.main(["doctor"])

    expected_lines = [
        "OK   Python: Python 3.11 is supported.",
        "WARN Bind address: Binding to all interfaces.",
    ]
    assert capsys.readouterr().out.splitlines() == expected_lines, (
        "the doctor command printed unexpected checks"
    )


@pytest.mark.usefixtures("failing_checks")
def test_doctor_fails_on_failed_checks() -> None:
    exit_code = cli.main(["doctor"])

    expected_exit_code = 1
    assert exit_code == expected_exit_code, "failed checks did not fail the command"


@pytest.mark.usefixtures("failing_checks")
@pytest.mark.parametrize(
    "expected_line",
    [
        "FAIL Tesseract: Executable not found.",
        "FAIL DjVuLibre: Executables not found.",
        (
            "sudo apt install tesseract-ocr tesseract-ocr-rus "
            "tesseract-ocr-eng djvulibre-bin"
        ),
        (
            "sudo dnf install tesseract tesseract-langpack-rus "
            "tesseract-langpack-eng djvulibre"
        ),
        "sudo pacman -S tesseract tesseract-data-rus tesseract-data-eng djvulibre",
    ],
    ids=["tesseract", "djvulibre", "apt", "dnf", "pacman"],
)
def test_doctor_fails_and_prints_native_tool_install_commands(
    capsys: pytest.CaptureFixture[str],
    expected_line: str,
) -> None:
    cli.main(["doctor"])

    assert expected_line in capsys.readouterr().out, (
        f"the doctor output lacks {expected_line!r}"
    )
