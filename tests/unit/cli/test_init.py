# Copyright (c) 2026 Nikolai Zelensky
"""Tests for the init command."""

import re
from pathlib import Path

import pytest

from audiodoc import cli

KEY_NAMES = ("AUDIODOC_AUDIO_KEY", "AUDIODOC_DOCUMENT_KEY")


@pytest.fixture(name="home")
def fixture_home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Point the application home at a directory that does not exist yet."""
    home = tmp_path / "дом audiodoc"
    monkeypatch.setenv("AUDIODOC_HOME", str(home))
    return home


def _env_values(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    return dict(re.findall(r"^([A-Z][A-Z_]*)=(.*)$", text, flags=re.MULTILINE))


def _keys(path: Path) -> tuple[str, str]:
    values = _env_values(path)
    return values[KEY_NAMES[0]], values[KEY_NAMES[1]]


def _init_rejected(arguments: list[str]) -> object:
    with pytest.raises(SystemExit) as caught:
        cli.main(arguments)
    return caught.value.code


def test_init_writes_the_chosen_options_and_disables_anonymous_access(
    home: Path,
) -> None:
    arguments = ["--model", "medium", "--device", "cuda", "--host", "10.8.0.1"]

    code = cli.main(["init", *arguments, "--port", "8123"])

    values = _env_values(home / ".env")
    observed = {
        "code": code,
        **{name: value for name, value in values.items() if name not in KEY_NAMES},
    }
    expected = {
        "code": 0,
        "ALLOW_UNAUTHENTICATED": "false",
        "AUDIODOC_HOST": "10.8.0.1",
        "AUDIODOC_PORT": "8123",
        "WHISPER_MODEL_SIZE": "medium",
        "WHISPER_DEVICE": "cuda",
        "WHISPER_COMPUTE_TYPE": "float16",
        "WHISPER_OFFLINE": "false",
    }
    assert observed == expected, "the configuration must hold the chosen options"


@pytest.mark.parametrize(
    ("arguments", "expected"),
    [
        (["--device", "cpu"], "int8"),
        (["--device", "cuda"], "float16"),
        (["--device", "cuda", "--compute-type", "int8_float16"], "int8_float16"),
    ],
)
def test_init_picks_the_compute_type_for_the_device(
    home: Path, arguments: list[str], expected: str
) -> None:
    cli.main(["init", *arguments])

    compute_type = _env_values(home / ".env")["WHISPER_COMPUTE_TYPE"]
    assert compute_type == expected, f"wrong compute type for {arguments}"


@pytest.mark.parametrize("name", KEY_NAMES)
def test_init_generates_long_url_safe_keys(home: Path, name: str) -> None:
    cli.main(["init"])

    key = _env_values(home / ".env")[name]
    assert re.fullmatch(r"[A-Za-z0-9_-]{43,}", key) is not None, f"weak {name}"


def test_init_generates_different_audio_and_document_keys(home: Path) -> None:
    cli.main(["init"])

    audio_key, document_key = _keys(home / ".env")
    assert audio_key != document_key, "one key must not open both APIs"


def test_init_makes_the_configuration_readable_only_by_the_owner(
    home: Path,
) -> None:
    cli.main(["init"])

    expected_mode = 0o600
    mode = (home / ".env").stat().st_mode & 0o777
    assert mode == expected_mode, "the .env holds keys and must be 0600"


def test_init_creates_a_private_home_directory(home: Path) -> None:
    cli.main(["init"])

    expected_mode = 0o700
    assert home.stat().st_mode & 0o777 == expected_mode, "the home must be 0700"


def test_init_leaves_no_temporary_file_behind(home: Path) -> None:
    cli.main(["init"])
    cli.main(["init", "--force"])

    expected = [".env"]
    assert sorted(path.name for path in home.iterdir()) == expected, "leftovers"


def test_init_refuses_to_overwrite_an_existing_configuration(home: Path) -> None:
    cli.main(["init"])
    original = (home / ".env").read_bytes()

    code = _init_rejected(["init", "--host", "192.168.77.5"])

    observed = (code, (home / ".env").read_bytes() == original)
    expected = (2, True)
    assert observed == expected, "an existing .env must stay unchanged"


def test_init_with_force_replaces_both_keys(home: Path) -> None:
    cli.main(["init"])
    old_keys = _keys(home / ".env")

    cli.main(["init", "--force"])

    new_keys = _keys(home / ".env")
    unchanged = [old for old, new in zip(old_keys, new_keys, strict=True) if old == new]
    expected_empty: list[str] = []
    assert unchanged == expected_empty, "--force must rotate both keys"


def test_init_refuses_a_symlinked_configuration_without_force(
    home: Path, tmp_path: Path
) -> None:
    target = tmp_path / "чужой.env"
    target.write_text("OPERATOR=keep\n", encoding="utf-8")
    home.mkdir()
    (home / ".env").symlink_to(target)

    code = _init_rejected(["init"])

    observed = (code, target.read_text(encoding="utf-8"))
    expected = (2, "OPERATOR=keep\n")
    assert observed == expected, "init must not write through a symlink"


def test_init_with_force_replaces_a_symlink_instead_of_its_target(
    home: Path, tmp_path: Path
) -> None:
    target = tmp_path / "чужой.env"
    target.write_text("OPERATOR=keep\n", encoding="utf-8")
    home.mkdir()
    (home / ".env").symlink_to(target)

    cli.main(["init", "--force"])

    observed = ((home / ".env").is_symlink(), target.read_text(encoding="utf-8"))
    expected = (False, "OPERATOR=keep\n")
    assert observed == expected, "--force must replace the link, not its target"
