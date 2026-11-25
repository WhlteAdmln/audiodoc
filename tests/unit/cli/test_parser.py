# Copyright (c) 2026 Nikolai Zelensky
"""Tests for the command-line argument parser."""

import pytest

from audiodoc.cli import build_parser


def test_rejects_out_of_range_run_port() -> None:
    with pytest.raises(SystemExit) as error:
        build_parser().parse_args(["run", "--port", "70000"])

    expected_code = 2
    assert error.value.code == expected_code, "out-of-range port did not exit with 2"


def test_reports_valid_run_port_range(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit):
        build_parser().parse_args(["run", "--port", "65536"])

    range_message = "between 1 and 65535"
    assert range_message in capsys.readouterr().err, "valid port range not reported"
