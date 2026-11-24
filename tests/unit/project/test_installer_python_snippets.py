# Copyright (c) 2026 Nikolai Zelensky
"""Regression tests for the Python snippets embedded in ``install.sh``."""

import hashlib
import json
import re
import runpy
import sys
from pathlib import Path

import pytest

INSTALLER = Path(__file__).resolve().parents[3] / "install.sh"
HEREDOC = re.compile(r"<<'PY'[^\n]*\n(.*?)\nPY\n", re.DOTALL)
RELEASE_SNIPPET = "release.get("
CHECKSUM_SNIPPET = "__NO_WHEEL__"
SETTINGS_SNIPPET = "Unexpected .env model settings"


def _snippets() -> list[str]:
    return HEREDOC.findall(INSTALLER.read_text(encoding="utf-8"))


def _run_snippet(
    marker: str,
    arguments: list[Path | str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> object:
    source = next(snippet for snippet in _snippets() if marker in snippet)
    script = tmp_path / "snippet.py"
    script.write_text(source, encoding="utf-8")
    monkeypatch.setattr(sys, "argv", [str(script), *(str(item) for item in arguments)])
    try:
        runpy.run_path(str(script), run_name="__main__")
    except SystemExit as exit_request:
        return exit_request.code
    return None


def _digest(seed: str) -> str:
    return hashlib.sha256(seed.encode()).hexdigest()


def test_installer_embeds_three_python_snippets() -> None:
    count = len(_snippets())

    expected_count = 3
    assert count == expected_count, "the snippet tests expect three here-documents"


def test_no_shell_command_follows_a_here_document_operator() -> None:
    lines = INSTALLER.read_text(encoding="utf-8").splitlines()

    offenders = [
        number + 2
        for number, line in enumerate(lines[:-1])
        if re.search(r"<<'PY'\s*(\|\||&&)\s*$", line)
        and lines[number + 1].startswith((" ", "\t"))
    ]

    expected_empty: list[int] = []
    assert offenders == expected_empty, "a command after <<'PY' joins the snippet"


def test_installer_messages_do_not_contain_broken_urls() -> None:
    text = INSTALLER.read_text(encoding="utf-8")

    split_url = "/insta\nll.sh"
    assert split_url not in text, "a URL in a message is split across lines"


def test_release_snippet_writes_tag_and_wheel_count(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "release.json"
    destination = tmp_path / "info.txt"
    release = {
        "tag_name": "v0.2.0",
        "draft": False,
        "assets": [
            {"name": "audiodoc-0.2.0-py3-none-any.whl"},
            {"name": "SHA256SUMS"},
        ],
    }
    source.write_text(json.dumps(release), encoding="utf-8")

    _run_snippet(RELEASE_SNIPPET, [source, destination], tmp_path, monkeypatch)

    lines = destination.read_text(encoding="utf-8").splitlines()
    expected = ["v0.2.0", "1"]
    assert lines == expected, "the tag and the wheel count must be written"


def test_release_snippet_counts_only_well_formed_wheel_assets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "релиз.json"
    destination = tmp_path / "info.txt"
    release = {
        "tag_name": "2026.11-rc+1",
        "assets": [
            {"name": "audiodoc-3.1-py3-none-any.whl"},
            "audiodoc-3.2-py3-none-any.whl",
            {"name": 7},
            {"name": "audiodoc-3.1-py3-none-any.whl.asc"},
            {"name": "other-3.1-py3-none-any.whl"},
            {"size": 12},
        ],
    }
    source.write_text(json.dumps(release), encoding="utf-8")

    _run_snippet(RELEASE_SNIPPET, [source, destination], tmp_path, monkeypatch)

    lines = destination.read_text(encoding="utf-8").splitlines()
    expected = ["2026.11-rc+1", "1"]
    assert lines == expected, "only dict assets named audiodoc-*.whl count"


@pytest.mark.parametrize(
    ("release", "message"),
    [
        ({"tag_name": "v1", "draft": True}, "Invalid release metadata"),
        ([{"tag_name": "v1"}], "Invalid release metadata"),
        ({"tag_name": "v1;id"}, "Invalid release tag"),
        ({"tag_name": "../v1"}, "Invalid release tag"),
        ({"tag_name": "-v1"}, "Invalid release tag"),
        ({"tag_name": "v1\nv2"}, "Invalid release tag"),
        ({"tag_name": 12}, "Invalid release tag"),
        ({"assets": []}, "Invalid release tag"),
    ],
)
def test_release_snippet_rejects_untrusted_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, release: object, message: str
) -> None:
    source = tmp_path / "release.json"
    destination = tmp_path / "info.txt"
    source.write_text(json.dumps(release), encoding="utf-8")

    code = _run_snippet(RELEASE_SNIPPET, [source, destination], tmp_path, monkeypatch)

    observed = (code, destination.exists())
    expected = (message, False)
    assert observed == expected, "untrusted metadata must stop the installer"


def test_checksum_snippet_keeps_only_the_wheel_and_constraints(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    source = tmp_path / "SHA256SUMS"
    destination = tmp_path / "verified"
    wheel_digest = _digest("wheel").upper()
    constraints_digest = _digest("constraints")
    source.write_text(
        f"{_digest('archive')}  audiodoc-4.0.zip\n"
        f"{wheel_digest}  audiodoc-4.0-py3-none-any.whl\n"
        f"{_digest('evil')}  ../audiodoc-6.6-py3-none-any.whl\n"
        f"{_digest('space')} audiodoc-5.0-py3-none-any.whl\n"
        f"{_digest('short')[:63]}  audiodoc-5.1-py3-none-any.whl\n"
        f"{constraints_digest}  constraints.txt\n",
        encoding="utf-8",
    )

    _run_snippet(CHECKSUM_SNIPPET, [source, destination], tmp_path, monkeypatch)

    observed = (capsys.readouterr().out, destination.read_text(encoding="utf-8"))
    expected = (
        "audiodoc-4.0-py3-none-any.whl\n",
        (
            f"{wheel_digest}  audiodoc-4.0-py3-none-any.whl\n"
            f"{constraints_digest}  constraints.txt\n"
        ),
    )
    assert observed == expected, "malformed and unsafe manifest lines must be ignored"


@pytest.mark.parametrize(
    ("names", "message"),
    [
        (
            ["audiodoc-1-py3-none-any.whl", "audiodoc-1-py3-none-any.whl"],
            "Duplicate SHA256SUMS entry: audiodoc-1-py3-none-any.whl",
        ),
        (
            [
                "audiodoc-1-py3-none-any.whl",
                "audiodoc-2-py3-none-any.whl",
                "constraints.txt",
            ],
            "SHA256SUMS must contain exactly one audiodoc wheel",
        ),
        (
            ["audiodoc-1-py3-none-any.whl"],
            "SHA256SUMS does not contain constraints.txt",
        ),
    ],
)
def test_checksum_snippet_rejects_an_ambiguous_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, names: list[str], message: str
) -> None:
    source = tmp_path / "SHA256SUMS"
    destination = tmp_path / "verified"
    lines = [f"{_digest(str(index))}  {name}" for index, name in enumerate(names)]
    source.write_text("\n".join(lines) + "\n", encoding="utf-8")

    code = _run_snippet(CHECKSUM_SNIPPET, [source, destination], tmp_path, monkeypatch)

    observed = (code, destination.exists())
    expected = (message, False)
    assert observed == expected, "an ambiguous manifest must be rejected"


def test_checksum_snippet_reports_a_manifest_without_a_wheel(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    source = tmp_path / "SHA256SUMS"
    destination = tmp_path / "verified"
    source.write_text(f"{_digest('c')}  constraints.txt\n", encoding="utf-8")

    code = _run_snippet(CHECKSUM_SNIPPET, [source, destination], tmp_path, monkeypatch)

    observed = (code, capsys.readouterr().out, destination.exists())
    expected = (0, "__NO_WHEEL__\n", False)
    assert observed == expected, "a manifest without a wheel must be reported"


def test_settings_snippet_rewrites_model_settings_and_keeps_other_lines(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text(
        "AUDIODOC_AUDIO_KEY=k3y=with=equals\n"
        "#WHISPER_OFFLINE=false\n"
        "WHISPER_MODEL_PATH=\n"
        "WHISPER_OFFLINE=false\n",
        encoding="utf-8",
    )
    model_path = '/srv/моя модель/"quoted"\\dir'

    _run_snippet(SETTINGS_SNIPPET, [env_path, model_path], tmp_path, monkeypatch)

    expected = (
        "AUDIODOC_AUDIO_KEY=k3y=with=equals\n"
        "#WHISPER_OFFLINE=false\n"
        'WHISPER_MODEL_PATH="/srv/моя модель/\\"quoted\\"\\\\dir"\n'
        "WHISPER_OFFLINE=true\n"
    )
    content = env_path.read_text(encoding="utf-8")
    assert content == expected, "the model path must be quoted and escaped"


def test_settings_snippet_keeps_the_settings_file_private(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text("WHISPER_MODEL_PATH=\nWHISPER_OFFLINE=0\n", encoding="utf-8")
    env_path.chmod(0o644)

    _run_snippet(SETTINGS_SNIPPET, [env_path, "/opt/m"], tmp_path, monkeypatch)

    expected_mode = 0o600
    assert env_path.stat().st_mode & 0o777 == expected_mode, "the .env must be 0600"


@pytest.mark.parametrize(
    "content",
    [
        "WHISPER_OFFLINE=false\n",
        "WHISPER_MODEL_PATH=\nWHISPER_MODEL_PATH=/x\nWHISPER_OFFLINE=false\n",
        "WHISPER_MODEL_PATH /x\nWHISPER_OFFLINE=false\n",
    ],
)
def test_settings_snippet_refuses_an_unexpected_settings_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, content: str
) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text(content, encoding="utf-8")

    code = _run_snippet(SETTINGS_SNIPPET, [env_path, "/opt/m"], tmp_path, monkeypatch)

    observed = (code, env_path.read_text(encoding="utf-8"))
    expected = (SETTINGS_SNIPPET, content)
    assert observed == expected, "an unexpected .env must stay unchanged"
