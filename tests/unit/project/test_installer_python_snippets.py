# Copyright (c) 2026 Nikolai Zelensky
"""Regression tests for the Python snippets embedded in ``install.sh``."""

import json
import re
import runpy
import sys
from pathlib import Path

import pytest

INSTALLER = Path(__file__).resolve().parents[3] / "install.sh"
HEREDOC = re.compile(r"<<'PY'[^\n]*\n(.*?)\nPY\n", re.DOTALL)


def _snippets() -> list[str]:
    """Return the Python source of every here-document in the installer."""
    return HEREDOC.findall(INSTALLER.read_text(encoding="utf-8"))


def test_installer_has_embedded_python_snippets() -> None:
    """The installer embeds the snippets this module protects."""
    assert len(_snippets()) >= 3


@pytest.mark.parametrize("index", range(3))
def test_every_embedded_snippet_is_valid_python(index: int) -> None:
    """A shell command placed inside a here-document would break the snippet."""
    compile(_snippets()[index], f"<install.sh snippet {index}>", "exec")


def test_no_shell_command_follows_a_here_document_operator() -> None:
    """The right side of ``||`` after ``<<'PY'`` must come after the terminator."""
    lines = INSTALLER.read_text(encoding="utf-8").splitlines()
    for number, line in enumerate(lines):
        if re.search(r"<<'PY'\s*(\|\||&&)\s*$", line):
            assert not lines[number + 1].startswith((" ", "\t")), number + 1


def test_release_metadata_snippet_extracts_tag_and_wheel_count(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The latest-release lookup parses a GitHub API response."""
    snippet = next(item for item in _snippets() if "release.get(" in item)
    source = tmp_path / "release.json"
    destination = tmp_path / "info.txt"
    source.write_text(
        json.dumps(
            {
                "tag_name": "v0.2.0",
                "draft": False,
                "assets": [
                    {"name": "audiodoc-0.2.0-py3-none-any.whl"},
                    {"name": "SHA256SUMS"},
                ],
            }
        ),
        encoding="utf-8",
    )

    snippet_path = tmp_path / "release_metadata.py"
    snippet_path.write_text(snippet, encoding="utf-8")
    monkeypatch.setattr(sys, "argv", [str(snippet_path), str(source), str(destination)])
    runpy.run_path(str(snippet_path), run_name="__main__")

    assert destination.read_text(encoding="utf-8").splitlines() == ["v0.2.0", "1"]


def test_installer_messages_do_not_contain_broken_urls() -> None:
    """A URL inside an error message must stay on one line."""
    text = INSTALLER.read_text(encoding="utf-8")

    assert "/insta\nll.sh" not in text
