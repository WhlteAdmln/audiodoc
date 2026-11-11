# Copyright (c) 2026 Nikolai Zelensky
"""Command-line interface tests."""

import logging
import runpy
from collections.abc import Iterable
from ipaddress import IPv4Address
from pathlib import Path
from types import SimpleNamespace

import pytest

from audiodoc import cli
from audiodoc.system_diagnostics import DiagnosticCheck


def _read_env_values(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line and not line.lstrip().startswith("#") and "=" in line:
            name, value = line.split("=", 1)
            values[name] = value
    return values


def test_version_prints_installed_package_version(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(cli, "package_version", lambda _name: "0.1.0")

    assert cli.main(["version"]) == 0
    assert capsys.readouterr().out == "audiodoc 0.1.0\n"


def test_run_loads_configuration_and_starts_uvicorn(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    calls: list[tuple[str, object]] = []
    env_file = tmp_path / "custom.env"
    all_interfaces_host = str(IPv4Address(0))

    def record_env_file(path: Path | None = None) -> None:
        calls.append(("env", path))

    def record_logging(level: str, secrets: Iterable[str]) -> None:
        calls.append(("logging", (level, tuple(secrets))))

    def record_uvicorn(application: str, **kwargs: object) -> None:
        calls.append(("uvicorn", (application, kwargs)))

    monkeypatch.setattr(cli, "load_env_file", record_env_file)
    monkeypatch.setattr(cli, "configure_logging", record_logging)
    monkeypatch.setattr(cli.uvicorn, "run", record_uvicorn)
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("AUDIODOC_AUDIO_KEY", "audio-secret, rotated-secret")
    monkeypatch.setenv("AUDIODOC_DOCUMENT_KEY", "document-secret")
    caplog.set_level(logging.WARNING, logger="audiodoc.cli")

    assert (
        cli.main(
            [
                "run",
                "--host",
                all_interfaces_host,
                "--port",
                "8123",
                "--env-file",
                str(env_file),
            ]
        )
        == 0
    )

    assert calls == [
        ("env", env_file),
        (
            "logging",
            ("DEBUG", ("audio-secret", "rotated-secret", "document-secret")),
        ),
        (
            "uvicorn",
            (
                "audiodoc.main:create_app",
                {
                    "factory": True,
                    "host": all_interfaces_host,
                    "port": 8123,
                    "server_header": False,
                },
            ),
        ),
    ]
    assert "SECURITY WARNING" in caplog.text
    assert all_interfaces_host in caplog.text


def test_run_defaults_to_loopback_and_port_8000(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, object]] = []
    monkeypatch.delenv("AUDIODOC_HOST", raising=False)
    monkeypatch.delenv("AUDIODOC_PORT", raising=False)

    def record_uvicorn(_application: str, **kwargs: object) -> None:
        calls.append(kwargs)

    monkeypatch.setattr(cli, "load_env_file", lambda _path=None: None)
    monkeypatch.setattr(cli, "configure_logging", lambda _level, _secrets: None)
    monkeypatch.setattr(cli.uvicorn, "run", record_uvicorn)

    assert cli.main(["run"]) == 0
    assert calls == [
        {
            "factory": True,
            "host": "127.0.0.1",
            "port": 8000,
            "server_header": False,
        }
    ]


def test_run_uses_bind_defaults_from_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, object]] = []
    monkeypatch.setenv("AUDIODOC_HOST", "10.8.0.1")
    monkeypatch.setenv("AUDIODOC_PORT", "8123")
    monkeypatch.setattr(cli, "load_env_file", lambda _path=None: None)
    monkeypatch.setattr(cli, "configure_logging", lambda _level, _secrets: None)
    monkeypatch.setattr(
        cli.uvicorn,
        "run",
        lambda _application, **kwargs: calls.append(kwargs),
    )

    assert cli.main(["run"]) == 0
    assert calls[0]["host"] == "10.8.0.1"
    assert calls[0]["port"] == 8123


def test_init_writes_distinct_keys_and_secure_configuration(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    monkeypatch.setenv("AUDIODOC_HOME", str(home))

    assert (
        cli.main(
            [
                "init",
                "--model",
                "medium",
                "--device",
                "cuda",
                "--host",
                "10.8.0.1",
                "--port",
                "8123",
            ]
        )
        == 0
    )

    env_path = home / ".env"
    values = _read_env_values(env_path)
    audio_key = values["AUDIODOC_AUDIO_KEY"]
    document_key = values["AUDIODOC_DOCUMENT_KEY"]

    assert len(audio_key) >= 43
    assert len(document_key) >= 43
    assert audio_key != document_key
    assert env_path.stat().st_mode & 0o777 == 0o600
    assert values["WHISPER_MODEL_SIZE"] == "medium"
    assert values["WHISPER_DEVICE"] == "cuda"
    assert values["WHISPER_COMPUTE_TYPE"] == "float16"
    assert values["AUDIODOC_HOST"] == "10.8.0.1"
    assert values["AUDIODOC_PORT"] == "8123"
    assert values["ALLOW_UNAUTHENTICATED"] == "false"


def test_init_refuses_to_overwrite_without_force_and_force_replaces(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    monkeypatch.setenv("AUDIODOC_HOME", str(home))

    assert cli.main(["init"]) == 0
    env_path = home / ".env"
    original = env_path.read_bytes()
    original_values = _read_env_values(env_path)

    with pytest.raises(SystemExit) as error:
        cli.main(["init"])

    assert error.value.code == 2
    assert env_path.read_bytes() == original

    assert cli.main(["init", "--force"]) == 0
    replacement_values = _read_env_values(env_path)
    assert (
        replacement_values["AUDIODOC_AUDIO_KEY"]
        != original_values["AUDIODOC_AUDIO_KEY"]
    )
    assert (
        replacement_values["AUDIODOC_DOCUMENT_KEY"]
        != original_values["AUDIODOC_DOCUMENT_KEY"]
    )


def test_pair_prints_exact_shared_settings_from_env_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    home = tmp_path / "home"
    monkeypatch.setenv("AUDIODOC_HOME", str(home))
    assert cli.main(["init"]) == 0
    capsys.readouterr()
    values = _read_env_values(home / ".env")
    monkeypatch.setenv("AUDIODOC_AUDIO_KEY", "environment-audio-key")
    monkeypatch.setenv("AUDIODOC_DOCUMENT_KEY", "environment-document-key")

    assert cli.main(["pair", "--url", "http://10.8.0.1:8000"]) == 0

    assert capsys.readouterr().out.splitlines() == [
        "AUDIODOC_URL=http://10.8.0.1:8000",
        f"AUDIODOC_AUDIO_KEY={values['AUDIODOC_AUDIO_KEY']}",
        f"AUDIODOC_DOCUMENT_KEY={values['AUDIODOC_DOCUMENT_KEY']}",
    ]


def test_pair_uses_host_and_port_from_env_when_url_is_omitted(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("AUDIODOC_HOME", str(tmp_path / "home"))
    assert cli.main(["init", "--host", "10.8.0.1", "--port", "8123"]) == 0
    capsys.readouterr()

    assert cli.main(["pair"]) == 0
    output = capsys.readouterr().out
    assert output.splitlines()[0] == "AUDIODOC_URL=http://10.8.0.1:8123"
    assert len(output.splitlines()) == 3


def test_model_download_uses_home_models_directory(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    home = tmp_path / "home"
    monkeypatch.setenv("AUDIODOC_HOME", str(home))
    calls: list[tuple[str, str]] = []

    def fake_download_model(name: str, *, output_dir: str) -> str:
        calls.append((name, output_dir))
        return output_dir

    monkeypatch.setattr(
        cli.importlib,
        "import_module",
        lambda _name: SimpleNamespace(download_model=fake_download_model),
    )

    assert cli.main(["model", "download"]) == 0
    expected_directory = home / "models" / "small"
    assert calls == [("small", str(expected_directory))]
    assert expected_directory.is_dir()
    assert capsys.readouterr().out == f"Model downloaded to: {expected_directory}\n"


def test_config_check_reports_valid_configuration(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(cli, "load_env_file", lambda _path=None: None)
    monkeypatch.setenv("ALLOW_UNAUTHENTICATED", "true")
    for name in (
        "AUDIODOC_AUDIO_KEY",
        "AUDIODOC_DOCUMENT_KEY",
        "WHISPER_API_KEY",
        "DOCUMENT_API_KEY",
    ):
        monkeypatch.delenv(name, raising=False)

    assert cli.main(["config", "check"]) == 0
    assert capsys.readouterr().out == "Configuration is valid.\n"


def test_config_check_collects_problems_without_printing_secrets(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(cli, "load_env_file", lambda _path=None: None)
    monkeypatch.setenv("WHISPER_API_KEY", "audio-secret")
    monkeypatch.setenv("WHISPER_CPU_THREADS", "secret-value")
    monkeypatch.setenv("WHISPER_OFFLINE", "sometimes")
    monkeypatch.setenv("MAX_AUDIO_SIZE", "0")
    monkeypatch.setenv("ALLOW_UNAUTHENTICATED", "invalid-secret-value")
    monkeypatch.setenv("LOG_LEVEL", "secret-log-level")
    for name in ("AUDIODOC_AUDIO_KEY", "AUDIODOC_DOCUMENT_KEY", "DOCUMENT_API_KEY"):
        monkeypatch.delenv(name, raising=False)

    assert cli.main(["config", "check"]) == 1
    output = capsys.readouterr().out

    for name in (
        "WHISPER_CPU_THREADS",
        "WHISPER_OFFLINE",
        "MAX_AUDIO_SIZE",
        "ALLOW_UNAUTHENTICATED",
        "AUDIODOC_DOCUMENT_KEY",
        "LOG_LEVEL",
    ):
        assert name in output

    for secret in (
        "audio-secret",
        "secret-value",
        "invalid-secret-value",
        "secret-log-level",
    ):
        assert secret not in output


def test_run_rejects_out_of_range_port(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as error:
        cli.main(["run", "--port", "70000"])

    assert error.value.code == 2
    assert "between 1 and 65535" in capsys.readouterr().err


def test_python_module_entry_point_invokes_main(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    entry_point = Path(__file__).resolve().parents[2] / "audiodoc" / "__main__.py"
    monkeypatch.setattr(cli, "main", lambda: 7)

    with pytest.raises(SystemExit) as error:
        runpy.run_path(str(entry_point), run_name="__main__")

    assert error.value.code == 7


def test_doctor_prints_checks_and_warnings_do_not_fail(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    calls: list[str] = []
    monkeypatch.setattr(cli, "load_env_file", lambda: calls.append("env"))
    monkeypatch.setattr(
        cli,
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
    monkeypatch.setattr(cli, "load_env_file", lambda: None)
    monkeypatch.setattr(
        cli,
        "collect_doctor_checks",
        lambda _environ: (
            DiagnosticCheck("Tesseract", "FAIL", "Executable not found."),
            DiagnosticCheck("DjVuLibre", "FAIL", "Executables not found."),
        ),
    )

    assert cli.main(["doctor"]) == 1
    output = capsys.readouterr().out

    assert "FAIL Tesseract: Executable not found." in output
    assert "FAIL DjVuLibre: Executables not found." in output
    assert (
        "sudo apt install tesseract-ocr tesseract-ocr-rus "
        "tesseract-ocr-eng djvulibre-bin"
    ) in output
    assert (
        "sudo dnf install tesseract tesseract-langpack-rus "
        "tesseract-langpack-eng djvulibre"
    ) in output
    assert (
        "sudo pacman -S tesseract tesseract-data-rus tesseract-data-eng djvulibre"
    ) in output
