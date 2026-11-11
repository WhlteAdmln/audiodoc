# Copyright (c) 2026 Nikolai Zelensky
"""Tests for system configuration diagnostics."""

from pathlib import Path
from typing import Self

import pytest

from audiodoc import system_diagnostics as diagnostics


def test_python_version_check_accepts_supported_version(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(diagnostics.sys, "version_info", (3, 11, 0))

    result = diagnostics.check_python_version()

    assert result.status == "OK"


def test_python_version_check_rejects_unsupported_version(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(diagnostics.sys, "version_info", (3, 10, 9))

    result = diagnostics.check_python_version()

    assert result.status == "FAIL"


def test_env_file_check_accepts_private_file(tmp_path: Path) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text("AUDIODOC_AUDIO_KEY=test\n", encoding="utf-8")
    env_path.chmod(0o600)

    result = diagnostics.check_env_file({"AUDIODOC_HOME": str(tmp_path)})

    assert result.status == "OK"


@pytest.mark.parametrize("permissions", [0o644, 0o000])
def test_env_file_check_rejects_insecure_permissions(
    tmp_path: Path, permissions: int
) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text("test\n", encoding="utf-8")
    env_path.chmod(permissions)

    result = diagnostics.check_env_file({"AUDIODOC_HOME": str(tmp_path)})

    assert result.status == "FAIL"
    assert "Permissions" in result.message


def test_env_file_check_rejects_missing_file(tmp_path: Path) -> None:
    result = diagnostics.check_env_file({"AUDIODOC_HOME": str(tmp_path)})

    assert result.status == "FAIL"
    assert "Not found" in result.message


def test_env_file_check_rejects_non_regular_file(tmp_path: Path) -> None:
    (tmp_path / ".env").mkdir()

    result = diagnostics.check_env_file({"AUDIODOC_HOME": str(tmp_path)})

    assert result.status == "FAIL"
    assert "regular file" in result.message


def test_env_file_check_reports_inspection_errors(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def fail_inspection(_path: Path) -> None:
        message = "denied"
        raise PermissionError(message)

    monkeypatch.setattr(Path, "lstat", fail_inspection)

    result = diagnostics.check_env_file({"AUDIODOC_HOME": str(tmp_path)})

    assert result.status == "FAIL"
    assert "Cannot inspect" in result.message


def test_api_key_check_accepts_distinct_keys_and_legacy_names() -> None:
    result = diagnostics.check_api_keys(
        {
            "WHISPER_API_KEY": "audio-one, audio-two",
            "DOCUMENT_API_KEY": "document-one",
        }
    )

    assert result.status == "OK"


@pytest.mark.parametrize(
    ("environ", "expected"),
    [
        ({}, "Missing API keys"),
        (
            {
                "AUDIODOC_AUDIO_KEY": "shared, audio",
                "AUDIODOC_DOCUMENT_KEY": "document, shared",
            },
            "share",
        ),
    ],
)
def test_api_key_check_rejects_missing_or_shared_keys(
    environ: dict[str, str], expected: str
) -> None:
    result = diagnostics.check_api_keys(environ)

    assert result.status == "FAIL"
    assert expected in result.message


def test_unauthenticated_check_accepts_disabled_setting() -> None:
    result = diagnostics.check_unauthenticated_setting(
        {"ALLOW_UNAUTHENTICATED": "false"}
    )

    assert result.status == "OK"


def test_unauthenticated_check_warns_when_enabled() -> None:
    result = diagnostics.check_unauthenticated_setting(
        {"ALLOW_UNAUTHENTICATED": "true"}
    )

    assert result.status == "WARN"


def test_unauthenticated_check_rejects_invalid_value() -> None:
    result = diagnostics.check_unauthenticated_setting(
        {"ALLOW_UNAUTHENTICATED": "sometimes"}
    )

    assert result.status == "FAIL"


def test_bind_address_check_accepts_loopback_default() -> None:
    result = diagnostics.check_bind_address({})

    assert result.status == "OK"


@pytest.mark.parametrize("host", sorted(diagnostics.ALL_INTERFACES_HOSTS))
def test_bind_address_check_warns_on_all_interfaces(host: str) -> None:
    result = diagnostics.check_bind_address({"AUDIODOC_HOST": host})

    assert result.status == "WARN"


def test_temp_directory_check_creates_and_writes_to_default_directory(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"

    result = diagnostics.check_temp_directory({"AUDIODOC_HOME": str(home)})

    assert result.status == "OK"
    assert (home / "tmp").is_dir()


def test_temp_directory_check_reports_unwritable_path(tmp_path: Path) -> None:
    invalid_path = tmp_path / "not-a-directory"
    invalid_path.write_text("file", encoding="utf-8")

    result = diagnostics.check_temp_directory(
        {
            "AUDIODOC_HOME": str(tmp_path),
            "BACKEND_TEMP_DIR": str(invalid_path),
        }
    )

    assert result.status == "FAIL"


class _FakeSocket:
    def __init__(self, *, unavailable: bool = False) -> None:
        self.unavailable = unavailable
        self.address: tuple[str, int] | None = None

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def bind(self, address: tuple[str, int]) -> None:
        self.address = address
        if self.unavailable:
            raise OSError


def test_port_check_accepts_available_port(monkeypatch: pytest.MonkeyPatch) -> None:
    listener = _FakeSocket()
    monkeypatch.setattr(diagnostics.socket, "socket", lambda *_args: listener)

    result = diagnostics.check_port({})

    assert result.status == "OK"
    assert listener.address == ("127.0.0.1", 8000)


def test_port_check_rejects_port_in_use(monkeypatch: pytest.MonkeyPatch) -> None:
    listener = _FakeSocket(unavailable=True)
    monkeypatch.setattr(diagnostics.socket, "socket", lambda *_args: listener)

    result = diagnostics.check_port({})

    assert result.status == "FAIL"


@pytest.mark.parametrize("port", ["invalid", "0", "65536"])
def test_port_check_rejects_invalid_port(port: str) -> None:
    result = diagnostics.check_port({"AUDIODOC_PORT": port})

    assert result.status == "FAIL"


def test_collect_system_checks_returns_all_check_results(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    env_path = home / ".env"
    env_path.write_text("test\n", encoding="utf-8")
    env_path.chmod(0o600)
    listener = _FakeSocket()
    monkeypatch.setattr(diagnostics.sys, "version_info", (3, 11, 0))
    monkeypatch.setattr(diagnostics.socket, "socket", lambda *_args: listener)

    checks = diagnostics.collect_system_checks(
        {
            "AUDIODOC_HOME": str(home),
            "AUDIODOC_AUDIO_KEY": "audio-secret",
            "AUDIODOC_DOCUMENT_KEY": "document-secret",
            "ALLOW_UNAUTHENTICATED": "false",
        }
    )

    assert [check.name for check in checks] == [
        "Python",
        "Environment file",
        "API keys",
        "Unauthenticated access",
        "Bind address",
        "Temporary directory",
        "API port",
    ]
    assert all(check.status == "OK" for check in checks)
