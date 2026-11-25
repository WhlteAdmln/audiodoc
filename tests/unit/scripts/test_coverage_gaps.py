# Copyright (c) 2026 Nikolai Zelensky

"""Tests for the coverage gap report script."""

from pathlib import Path

import pytest

from scripts.coverage_gaps import find_coverage_gaps, main


def _write_report(path: Path, classes: str) -> None:
    path.write_text(
        "<coverage><sources><source>/repo/audiodoc</source></sources>"
        "<packages><package><classes>"
        f"{classes}"
        "</classes></package></packages></coverage>",
        encoding="utf-8",
    )


def test_find_coverage_gaps_combines_statement_and_branch_coverage(
    tmp_path: Path,
) -> None:
    report = tmp_path / "coverage.xml"
    _write_report(
        report,
        """
        <class name="branchy.py" filename="branchy.py">
            <lines>
                <line number="1" hits="1"/>
                <line number="2" hits="0"/>
                <line number="3" hits="1" branch="true"
                      condition-coverage="50% (1/2)"/>
            </lines>
        </class>
        <class name="plain.py" filename="plain.py">
            <lines>
                <line number="1" hits="0"/>
                <line number="2" hits="1"/>
            </lines>
        </class>
        """,
    )

    expected_gaps = [
        (50.0, "audiodoc/plain.py"),
        (60.0, "audiodoc/branchy.py"),
    ]
    assert find_coverage_gaps(report) == expected_gaps, "wrong coverage gaps"


@pytest.fixture(name="dtd_report_arguments")
def fixture_dtd_report_arguments(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Point the command line at a report with a DTD declaration."""
    report = tmp_path / "coverage.xml"
    report.write_text(
        '<!DOCTYPE coverage [<!ENTITY payload "value">]>'
        "<coverage><sources/><packages/></coverage>",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "sys.argv",
        ["coverage_gaps.py", "--xml", str(report)],
    )


@pytest.fixture(name="limited_report_arguments")
def fixture_limited_report_arguments(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Point the command line at a one-file report with a limit of one."""
    report = tmp_path / "coverage.xml"
    _write_report(
        report,
        """
        <class name="plain.py" filename="plain.py">
            <lines>
                <line number="1" hits="0"/>
                <line number="2" hits="1"/>
            </lines>
        </class>
        """,
    )
    monkeypatch.setattr(
        "sys.argv",
        ["coverage_gaps.py", "--xml", str(report), "--limit", "1"],
    )


def test_find_coverage_gaps_returns_at_most_fifteen_files(tmp_path: Path) -> None:
    report = tmp_path / "coverage.xml"
    classes = "".join(
        f'<class name="file_{index:02d}.py" filename="file_{index:02d}.py">'
        '<lines><line number="1" hits="0"/></lines></class>'
        for index in range(16)
    )
    _write_report(report, classes)

    results = find_coverage_gaps(report)

    expected_filenames = [f"audiodoc/file_{index:02d}.py" for index in range(15)]
    assert [filename for _, filename in results] == expected_filenames, (
        "wrong number or order of reported files"
    )


def test_find_coverage_gaps_rejects_invalid_branch_coverage(tmp_path: Path) -> None:
    report = tmp_path / "coverage.xml"
    _write_report(
        report,
        """
        <class name="branchy.py" filename="branchy.py">
            <lines>
                <line number="1" hits="1" branch="true"
                      condition-coverage="invalid"/>
            </lines>
        </class>
        """,
    )

    with pytest.raises(ValueError, match="Invalid branch coverage") as error:
        find_coverage_gaps(report)

    expected_message = "Invalid branch coverage metadata"
    assert str(error.value) == expected_message, "wrong invalid metadata error"


@pytest.mark.usefixtures("dtd_report_arguments")
def test_main_rejects_dtd_declarations() -> None:
    expected_code = 1
    assert main() == expected_code, "a DTD declaration was accepted"


@pytest.mark.usefixtures("dtd_report_arguments")
def test_main_reports_rejected_dtd_declarations_as_error(
    capsys: pytest.CaptureFixture[str],
) -> None:
    main()

    error_prefix = "ERROR:"
    assert capsys.readouterr().err.startswith(error_prefix), "no error was printed"


@pytest.mark.usefixtures("limited_report_arguments")
def test_main_succeeds_with_a_file_limit() -> None:
    expected_code = 0
    assert main() == expected_code, "the report command did not succeed"


@pytest.mark.usefixtures("limited_report_arguments")
def test_main_prints_requested_number_of_files(
    capsys: pytest.CaptureFixture[str],
) -> None:
    main()

    expected_out = "Files with lowest coverage (up to 1):\n 50.000% audiodoc/plain.py\n"
    assert capsys.readouterr().out == expected_out, "wrong report output"
