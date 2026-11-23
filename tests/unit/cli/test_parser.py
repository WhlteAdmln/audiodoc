# Copyright (c) 2026 Nikolai Zelensky
"""Tests for the command-line argument parser."""

import pytest

from audiodoc.cli import build_parser


def test_rejects_out_of_range_run_port(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as error:
        build_parser().parse_args(["run", "--port", "70000"])

    expected_code = 2
    assert error.value.code == expected_code
    expected_fragment = "between 1 and 65535"
    assert expected_fragment in capsys.readouterr().err
