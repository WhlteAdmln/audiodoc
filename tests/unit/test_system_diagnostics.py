# Copyright (c) 2026 Nikolai Zelensky
"""Tests for system configuration diagnostics."""

import errno
import ipaddress
from pathlib import Path

import pytest

from audiodoc import system_diagnostics as diagnostics
from audiodoc.system_diagnostics import DiagnosticCheck
from tests.support.http_connections import FakeHealthServer
from tests.support.sockets import FakeSocket


def _write_env(home: Path, permissions: int) -> Path:
    home.mkdir(parents=True, exist_ok=True)
    env_path = home / ".env"
    env_path.write_text("AUDIODOC_AUDIO_KEY=a9-Zq\n", encoding="utf-8")
    env_path.chmod(permissions)
    return env_path


def _fail_inspection(_path: Path) -> None:
    message = "denied by policy"
    raise PermissionError(message)


@pytest.fixture(name="free_listener")
def fixture_free_listener(monkeypatch: pytest.MonkeyPatch) -> FakeSocket:
    """Make every socket bind succeed and record the probed address."""
    listener = FakeSocket()
    monkeypatch.setattr(diagnostics.socket, "socket", lambda *_args: listener)
    return listener


@pytest.fixture(name="busy_listener")
def fixture_busy_listener(monkeypatch: pytest.MonkeyPatch) -> FakeSocket:
    """Make every socket bind fail as if the port were in use."""
    listener = FakeSocket(bind_errno=errno.EADDRINUSE)
    monkeypatch.setattr(diagnostics.socket, "socket", lambda *_args: listener)
    return listener


@pytest.fixture(name="audiodoc_server")
def fixture_audiodoc_server(monkeypatch: pytest.MonkeyPatch) -> FakeHealthServer:
    """Answer the health probe like a running audiodoc service."""
    body = b'{"status": "ok", "model": "small", "loaded": true}'
    server = FakeHealthServer(body=body)
    monkeypatch.setattr(diagnostics, "HTTPConnection", server.connect)
    return server


@pytest.fixture(name="closed_server")
def fixture_closed_server(monkeypatch: pytest.MonkeyPatch) -> FakeHealthServer:
    """Refuse every health probe connection."""
    server = FakeHealthServer(refused=True)
    monkeypatch.setattr(diagnostics, "HTTPConnection", server.connect)
    return server


@pytest.mark.parametrize(
    ("version", "expected"),
    [
        (
            (3, 11, 5),
            DiagnosticCheck("Python", "OK", "Python 3.11.5 is supported."),
        ),
        (
            (4, 0, 2),
            DiagnosticCheck("Python", "OK", "Python 4.0.2 is supported."),
        ),
        (
            (3, 11, 4),
            DiagnosticCheck(
                "Python", "FAIL", "Python 3.11.5 or newer is required; found 3.11.4."
            ),
        ),
        (
            (3, 10, 9),
            DiagnosticCheck(
                "Python", "FAIL", "Python 3.11.5 or newer is required; found 3.10.9."
            ),
        ),
        (
            (2, 7, 18),
            DiagnosticCheck(
                "Python", "FAIL", "Python 3.11.5 or newer is required; found 2.7.18."
            ),
        ),
    ],
)
def test_reports_python_version_support(
    monkeypatch: pytest.MonkeyPatch,
    version: tuple[int, int, int],
    expected: DiagnosticCheck,
) -> None:
    monkeypatch.setattr(diagnostics.sys, "version_info", version)

    result = diagnostics.check_python_version()

    assert result == expected, "wrong Python version verdict"


@pytest.mark.parametrize("permissions", [0o600, 0o400, 0o700])
def test_accepts_private_env_file(tmp_path: Path, permissions: int) -> None:
    env_path = _write_env(tmp_path, permissions)

    result = diagnostics.check_env_file({"AUDIODOC_HOME": str(tmp_path)})

    expected = DiagnosticCheck(
        "Environment file", "OK", f"Found with private permissions: {env_path}."
    )
    assert result == expected, "a private .env file must pass"


def test_accepts_env_file_in_home_with_unusual_name(tmp_path: Path) -> None:
    home = tmp_path / "дом с пробелом; $(id)"
    env_path = _write_env(home, 0o600)

    result = diagnostics.check_env_file({"AUDIODOC_HOME": str(home)})

    expected = DiagnosticCheck(
        "Environment file", "OK", f"Found with private permissions: {env_path}."
    )
    assert result == expected, "an unusual home path must not break the check"


@pytest.mark.parametrize(
    "permissions", [0o644, 0o000, 0o640, 0o604, 0o620, 0o602, 0o610, 0o200, 0o777]
)
def test_rejects_env_file_with_insecure_permissions(
    tmp_path: Path, permissions: int
) -> None:
    env_path = _write_env(tmp_path, permissions)

    result = diagnostics.check_env_file({"AUDIODOC_HOME": str(tmp_path)})

    expected = DiagnosticCheck(
        "Environment file",
        "FAIL",
        f"Permissions must be private and owner-readable: {env_path}.",
    )
    assert result == expected, "a shared or unreadable .env file must fail"


def test_rejects_missing_env_file(tmp_path: Path) -> None:
    result = diagnostics.check_env_file({"AUDIODOC_HOME": str(tmp_path)})

    expected = DiagnosticCheck(
        "Environment file", "FAIL", f"Not found: {tmp_path / '.env'}."
    )
    assert result == expected, "a missing .env file must fail"


def test_rejects_env_directory(tmp_path: Path) -> None:
    env_path = tmp_path / ".env"
    env_path.mkdir()

    result = diagnostics.check_env_file({"AUDIODOC_HOME": str(tmp_path)})

    expected = DiagnosticCheck(
        "Environment file", "FAIL", f"Not a regular file: {env_path}."
    )
    assert result == expected, "a directory named .env must fail"


def test_rejects_env_symlink_to_private_file(tmp_path: Path) -> None:
    target = _write_env(tmp_path / "elsewhere", 0o600)
    home = tmp_path / "home"
    home.mkdir()
    env_path = home / ".env"
    env_path.symlink_to(target)

    result = diagnostics.check_env_file({"AUDIODOC_HOME": str(home)})

    expected = DiagnosticCheck(
        "Environment file", "FAIL", f"Not a regular file: {env_path}."
    )
    assert result == expected, "a symlinked .env file must not be followed"


def test_reports_env_file_inspection_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(Path, "lstat", _fail_inspection)

    result = diagnostics.check_env_file({"AUDIODOC_HOME": str(tmp_path)})

    expected = DiagnosticCheck(
        "Environment file",
        "FAIL",
        f"Cannot inspect {tmp_path / '.env'}: denied by policy.",
    )
    assert result == expected, "an unreadable .env path must fail with the reason"


@pytest.mark.parametrize(
    "environ",
    [
        {
            "AUDIODOC_AUDIO_KEY": "audio-one, audio-two",
            "AUDIODOC_DOCUMENT_KEY": "document-one",
        },
        {"AUDIODOC_AUDIO_KEY": "Key-7Ab", "AUDIODOC_DOCUMENT_KEY": "key-7ab"},
        {"AUDIODOC_AUDIO_KEY": " aud-8x ,, ", "AUDIODOC_DOCUMENT_KEY": "doc~42"},
    ],
)
def test_accepts_distinct_api_keys(environ: dict[str, str]) -> None:
    result = diagnostics.check_api_keys(environ)

    expected = DiagnosticCheck(
        "API keys", "OK", "Both API keys are present and distinct."
    )
    assert result == expected, "distinct audio and document keys must pass"


@pytest.mark.parametrize(
    ("environ", "expected_message"),
    [
        ({}, "Missing API keys: AUDIODOC_AUDIO_KEY, AUDIODOC_DOCUMENT_KEY."),
        (
            {"AUDIODOC_AUDIO_KEY": " , ,\t", "AUDIODOC_DOCUMENT_KEY": "doc-Q1"},
            "Missing API keys: AUDIODOC_AUDIO_KEY.",
        ),
        (
            {"AUDIODOC_AUDIO_KEY": "aud-Z9", "AUDIODOC_DOCUMENT_KEY": ""},
            "Missing API keys: AUDIODOC_DOCUMENT_KEY.",
        ),
        (
            {
                "AUDIODOC_AUDIO_KEY": "shared, audio",
                "AUDIODOC_DOCUMENT_KEY": "document, shared",
            },
            "The audio and document API keys share at least one value.",
        ),
        (
            {"AUDIODOC_AUDIO_KEY": "s3cr3t", "AUDIODOC_DOCUMENT_KEY": "  s3cr3t  "},
            "The audio and document API keys share at least one value.",
        ),
        (
            {"AUDIODOC_AUDIO_KEY": "aud-K3", "AUDIODOC_DOCUMENT_KEY": "doc-ключ-7"},
            "API keys must contain only ASCII characters: AUDIODOC_DOCUMENT_KEY.",
        ),
        (
            {"AUDIODOC_AUDIO_KEY": " ключ-один ,, ", "AUDIODOC_DOCUMENT_KEY": "dоc-5"},
            (
                "API keys must contain only ASCII characters: "
                "AUDIODOC_AUDIO_KEY, AUDIODOC_DOCUMENT_KEY."
            ),
        ),
        (
            {"AUDIODOC_AUDIO_KEY": "naïve, naïve", "AUDIODOC_DOCUMENT_KEY": "naïve"},
            (
                "API keys must contain only ASCII characters: "
                "AUDIODOC_AUDIO_KEY, AUDIODOC_DOCUMENT_KEY."
            ),
        ),
    ],
)
def test_rejects_missing_non_ascii_or_shared_api_keys(
    environ: dict[str, str], expected_message: str
) -> None:
    result = diagnostics.check_api_keys(environ)

    expected = DiagnosticCheck("API keys", "FAIL", expected_message)
    assert result == expected, "missing, non-ASCII or shared keys must fail"


@pytest.mark.parametrize(
    ("value", "expected_status"),
    [
        ("false", "OK"),
        ("", "OK"),
        (" Off ", "OK"),
        ("true", "WARN"),
        (" YES ", "WARN"),
        ("1", "WARN"),
        ("sometimes", "FAIL"),
        ("true!", "FAIL"),
        ("2", "FAIL"),
    ],
)
def test_classifies_unauthenticated_setting(value: str, expected_status: str) -> None:
    result = diagnostics.check_unauthenticated_setting({"ALLOW_UNAUTHENTICATED": value})

    assert result.status == expected_status, "wrong verdict for the auth bypass"


@pytest.mark.parametrize(
    ("environ", "expected_message"),
    [
        ({}, "Server binds to 127.0.0.1."),
        ({"AUDIODOC_HOST": "   "}, "Server binds to 127.0.0.1."),
        ({"AUDIODOC_HOST": "192.168.17.4"}, "Server binds to 192.168.17.4."),
        ({"AUDIODOC_HOST": "::1"}, "Server binds to ::1."),
        ({"AUDIODOC_HOST": "localhost"}, "Server binds to localhost."),
        ({"AUDIODOC_HOST": "fe80::7%lo0"}, "Server binds to fe80::7%lo0."),
        (
            {"AUDIODOC_HOST": "x" * 70 + ".example"},
            f"Server binds to {'x' * 70}.example.",
        ),
    ],
)
def test_accepts_specific_bind_address(
    environ: dict[str, str], expected_message: str
) -> None:
    result = diagnostics.check_bind_address(environ)

    expected = DiagnosticCheck("Bind address", "OK", expected_message)
    assert result == expected, "a specific bind address must pass"


@pytest.mark.parametrize(
    "host",
    [
        str(ipaddress.IPv4Address(0)),
        str(ipaddress.IPv6Address(0)),
        f" {ipaddress.IPv4Address(0)}\t",
        "0",
        "::0",
        "0:0:0:0:0:0:0:0",
        "000.0",
        "0x0",
    ],
)
def test_warns_on_all_interfaces_bind_address(host: str) -> None:
    result = diagnostics.check_bind_address({"AUDIODOC_HOST": host})

    expected_status = "WARN"
    assert result.status == expected_status, "binding to every interface must warn"


def test_reports_default_temp_directory_as_writable(tmp_path: Path) -> None:
    home = tmp_path / "home"

    result = diagnostics.check_temp_directory({"AUDIODOC_HOME": str(home)})

    expected = DiagnosticCheck(
        "Temporary directory", "OK", f"Writable: {home / 'tmp'}."
    )
    assert result == expected, "the default temporary directory must pass"


def test_creates_default_temp_directory(tmp_path: Path) -> None:
    home = tmp_path / "home-Ω"

    diagnostics.check_temp_directory({"AUDIODOC_HOME": str(home)})

    assert (home / "tmp").is_dir(), "the temporary directory was not created"


def test_creates_temp_directory_private_to_owner(tmp_path: Path) -> None:
    home = tmp_path / "home-perm"

    diagnostics.check_temp_directory({"AUDIODOC_HOME": str(home)})

    expected_mode = 0o700
    actual_mode = (home / "tmp").stat().st_mode & 0o777
    assert actual_mode == expected_mode, "the temporary directory is not private"


def test_resolves_relative_temp_directory_under_home(tmp_path: Path) -> None:
    home = tmp_path / "home-rel"

    result = diagnostics.check_temp_directory(
        {"AUDIODOC_HOME": str(home), "BACKEND_TEMP_DIR": " scratch/../work "}
    )

    expected = DiagnosticCheck(
        "Temporary directory", "OK", f"Writable: {home / 'scratch/../work'}."
    )
    assert result == expected, "a relative temporary directory must use the home"


def test_rejects_temp_directory_that_is_a_file(tmp_path: Path) -> None:
    invalid_path = tmp_path / "not-a-directory"
    invalid_path.write_text("plain file", encoding="utf-8")

    result = diagnostics.check_temp_directory(
        {"AUDIODOC_HOME": str(tmp_path), "BACKEND_TEMP_DIR": str(invalid_path)}
    )

    expected = ("Temporary directory", "FAIL")
    assert (result.name, result.status) == expected, "a file path must fail"


def test_reports_available_port(free_listener: FakeSocket) -> None:
    result = diagnostics.check_port({})

    expected = DiagnosticCheck("API port", "OK", "Port 8000 on 127.0.0.1 is available.")
    assert (result, free_listener.address) == (expected, ("127.0.0.1", 8000)), (
        "the default port must be probed and pass"
    )


def test_probes_configured_ipv6_host_and_port(free_listener: FakeSocket) -> None:
    diagnostics.check_port({"AUDIODOC_HOST": " ::1 ", "AUDIODOC_PORT": " 8443 "})

    expected_address = ("::1", 8443)
    assert free_listener.address == expected_address, "wrong address was probed"


@pytest.mark.usefixtures("closed_server")
def test_rejects_port_in_use(busy_listener: FakeSocket) -> None:
    result = diagnostics.check_port({"AUDIODOC_PORT": "65535"})

    expected = ("API port", "FAIL", ("127.0.0.1", 65535))
    assert (result.name, result.status, busy_listener.address) == expected, (
        "a busy port must fail"
    )


@pytest.mark.usefixtures("busy_listener")
def test_accepts_port_held_by_running_service(
    audiodoc_server: FakeHealthServer,
) -> None:
    result = diagnostics.check_port({"AUDIODOC_PORT": "18731"})

    expected = DiagnosticCheck(
        "API port",
        "OK",
        "Port 18731 on 127.0.0.1 is used by the running audiodoc service.",
    )
    assert (result, audiodoc_server.path) == (expected, "/health"), (
        "a port held by audiodoc must pass after the health probe"
    )


@pytest.mark.usefixtures("busy_listener")
def test_probes_health_on_configured_address(
    audiodoc_server: FakeHealthServer,
) -> None:
    diagnostics.check_port({"AUDIODOC_HOST": " fd12::7 ", "AUDIODOC_PORT": "9441"})

    expected_address = ("fd12::7", 9441)
    assert audiodoc_server.address == expected_address, "wrong address was probed"


@pytest.mark.parametrize(
    ("status", "body"),
    [
        (503, b'{"status": "ok", "loaded": false}'),
        (200, b"<html>nginx</html>"),
        (200, b"\xff\xfe\x00"),
        (200, b'{"status": "degraded", "loaded": true}'),
        (200, b'{"status": "ok"}'),
        (200, b'["ok", "loaded"]'),
    ],
)
@pytest.mark.usefixtures("busy_listener")
def test_rejects_busy_port_without_audiodoc_health(
    monkeypatch: pytest.MonkeyPatch, status: int, body: bytes
) -> None:
    server = FakeHealthServer(status=status, body=body)
    monkeypatch.setattr(diagnostics, "HTTPConnection", server.connect)

    result = diagnostics.check_port({"AUDIODOC_PORT": "7077"})

    expected_status = "FAIL"
    assert result.status == expected_status, "a foreign listener must fail"


def test_skips_health_probe_when_bind_fails_otherwise(
    monkeypatch: pytest.MonkeyPatch, audiodoc_server: FakeHealthServer
) -> None:
    listener = FakeSocket(bind_errno=errno.EACCES)
    monkeypatch.setattr(diagnostics.socket, "socket", lambda *_args: listener)

    result = diagnostics.check_port({"AUDIODOC_PORT": "443"})

    expected = ("FAIL", None)
    assert (result.status, audiodoc_server.address) == expected, (
        "only an address in use may be probed over HTTP"
    )


@pytest.mark.parametrize(
    ("port", "expected_message"),
    [
        ("invalid", "AUDIODOC_PORT must be an integer."),
        ("", "AUDIODOC_PORT must be an integer."),
        ("80 80", "AUDIODOC_PORT must be an integer."),
        ("1e3", "AUDIODOC_PORT must be an integer."),
        ("0", "AUDIODOC_PORT must be between 1 and 65535."),
        ("-22", "AUDIODOC_PORT must be between 1 and 65535."),
        ("65536", "AUDIODOC_PORT must be between 1 and 65535."),
        ("9" * 40, "AUDIODOC_PORT must be between 1 and 65535."),
    ],
)
def test_rejects_invalid_port(port: str, expected_message: str) -> None:
    result = diagnostics.check_port({"AUDIODOC_PORT": port})

    expected = DiagnosticCheck("API port", "FAIL", expected_message)
    assert result == expected, "an invalid port must fail"


def test_collects_every_check_in_order(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, free_listener: FakeSocket
) -> None:
    home = tmp_path / "home"
    _write_env(home, 0o600)
    monkeypatch.setattr(diagnostics.sys, "version_info", (3, 12, 1))

    checks = diagnostics.collect_system_checks(
        {
            "AUDIODOC_HOME": str(home),
            "AUDIODOC_AUDIO_KEY": "audio-secret",
            "AUDIODOC_DOCUMENT_KEY": "document-secret",
            "ALLOW_UNAUTHENTICATED": "false",
        }
    )

    expected = [
        ("Python", "OK"),
        ("Environment file", "OK"),
        ("API keys", "OK"),
        ("Unauthenticated access", "OK"),
        ("Bind address", "OK"),
        ("Temporary directory", "OK"),
        ("API port", "OK"),
    ]
    actual = [(check.name, check.status) for check in checks]
    assert (actual, free_listener.address) == (expected, ("127.0.0.1", 8000)), (
        "a healthy installation must pass every check"
    )
