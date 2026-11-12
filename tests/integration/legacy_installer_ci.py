# Copyright (c) 2026 Nikolai Zelensky
"""CI integration tests for upgrading a v0.1.0 directory installation."""

import functools
import hashlib
import http.server
import os
import shutil
import socket
import threading
import venv
from collections.abc import Iterator
from pathlib import Path

import pytest

from tests.unit.test_installer import create_systemctl_stub, run_installer

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RELEASE_DIR = PROJECT_ROOT / "dist"
LEGACY_SOURCE_FILES = (
    "backend/main.py",
    "app.py",
    "deploy/audiodoc.service.example",
    "scripts/build_release.sh",
    "docs/operations.md",
    "requirements.txt",
    "requirements-dev.txt",
    "requirements-lock.txt",
    "install.sh",
    "README.md",
    "README.ru.md",
    "LICENSE",
    ".env.example",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _tree_hashes(directory: Path) -> dict[str, str]:
    return {
        path.relative_to(directory).as_posix(): _sha256(path)
        for path in sorted(directory.rglob("*"))
        if path.is_file()
    }


def _legacy_source_hashes(directory: Path) -> dict[str, str]:
    return {relative: _sha256(directory / relative) for relative in LEGACY_SOURCE_FILES}


def _preserved_hashes(app_home: Path) -> dict[str, str]:
    hashes = {".env": _sha256(app_home / ".env")}
    for directory_name in ("models", "tmp"):
        hashes.update(
            {
                f"{directory_name}/{relative}": digest
                for relative, digest in _tree_hashes(app_home / directory_name).items()
            }
        )
    return hashes


def _prepare_legacy_installation(
    legacy_source: Path,
    app_home: Path,
    *,
    doctor_failure: bool = False,
) -> dict[str, str]:
    shutil.copytree(
        legacy_source,
        app_home,
        ignore=shutil.ignore_patterns(".git"),
    )
    venv.EnvBuilder(with_pip=True).create(str(app_home / ".venv"))

    model_dir = app_home / "models" / "ci-legacy-model"
    model_dir.mkdir(parents=True)
    (model_dir / "config.json").write_text("{}", encoding="utf-8")
    (model_dir / "model.bin").write_bytes(b"legacy-model-marker")

    tmp_dir = app_home / "tmp"
    tmp_dir.mkdir()
    (tmp_dir / "legacy.tmp").write_bytes(b"legacy-temporary-marker")

    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]

    audio_key = "ci-legacy-audio-key-not-a-real-secret"
    document_key = (
        audio_key if doctor_failure else "ci-legacy-document-key-not-a-real-secret"
    )
    updates = {
        "WHISPER_API_KEY": audio_key,
        "DOCUMENT_API_KEY": document_key,
        "BACKEND_TEMP_DIR": str(tmp_dir),
        "WHISPER_MODEL_PATH": str(model_dir),
        "WHISPER_OFFLINE": "true",
    }

    template = (app_home / ".env.example").read_text(encoding="utf-8")
    lines: list[str] = []
    seen: set[str] = set()

    for line in template.splitlines():
        name, separator, _value = line.partition("=")
        if separator and name in updates:
            lines.append(f'{name}="{updates[name]}"')
            seen.add(name)
        else:
            lines.append(line)

    missing_keys = set(updates) - seen
    assert seen == set(updates), (
        f"Legacy .env.example is missing keys: {', '.join(sorted(missing_keys))}"
    )

    lines.extend(
        (
            f"AUDIODOC_PORT={port}",
            "LEGACY_UPGRADE_MARKER=preserve-me",
        )
    )
    env_path = app_home / ".env"
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    env_path.chmod(0o600)

    return _legacy_source_hashes(app_home)


def _create_legacy_user_unit(user_home: Path, app_home: Path) -> tuple[Path, str]:
    unit_directory = user_home / ".config" / "systemd" / "user"
    unit_directory.mkdir(parents=True)
    unit_path = unit_directory / "audiodoc.service"

    old_unit = (
        "[Unit]\n"
        "Description=Legacy audiodoc API service\n\n"
        "[Service]\n"
        f"WorkingDirectory={app_home}\n"
        f"EnvironmentFile={app_home}/.env\n"
        f"ExecStart={app_home}/.venv/bin/uvicorn app:app\n\n"
        "[Install]\n"
        "WantedBy=default.target\n"
    )
    unit_path.write_text(old_unit, encoding="utf-8")

    return unit_path, old_unit


def _site_packages(app_home: Path) -> Path:
    candidates = list((app_home / ".venv" / "lib").glob("python*/site-packages"))
    assert len(candidates) == 1
    return candidates[0]


def _assert_app_imports_from_wheel(app_home: Path) -> None:
    site_packages = _site_packages(app_home)
    wheel_module = site_packages / "app.py"
    assert wheel_module.is_file()

    result = run_installer(
        command=[
            str(app_home / ".venv" / "bin" / "python"),
            "-c",
            "import app; from pathlib import Path; print(Path(app.__file__).resolve())",
        ],
        home=app_home.parent,
        app_home=app_home,
    )
    assert result.returncode == 0, result.stdout + result.stderr

    imported_module = Path(result.stdout.strip()).resolve()
    assert imported_module == wheel_module.resolve()
    assert imported_module != (app_home / ".legacy-0.1.0" / "app.py").resolve()


def _assert_doctor_is_green(output: str) -> None:
    lines = output.splitlines()
    assert "FAIL" not in output

    for check_name in ("API keys", "Whisper model", "Tesseract", "DjVuLibre"):
        assert any(
            line.startswith("OK") and f"{check_name}:" in line for line in lines
        ), output


@pytest.fixture
def local_release_server() -> Iterator[str]:
    assert RELEASE_DIR.is_dir()
    assert len(list(RELEASE_DIR.glob("audiodoc-*.whl"))) == 1
    assert (RELEASE_DIR / "constraints.txt").is_file()
    assert (RELEASE_DIR / "SHA256SUMS").is_file()

    handler = functools.partial(
        http.server.SimpleHTTPRequestHandler,
        directory=str(RELEASE_DIR),
    )
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def _prepare_ci_environment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[Path, dict[str, str], Path]:
    """Configure isolated environment variables and systemctl."""
    legacy_source = Path(os.environ["AUDIODOC_LEGACY_SOURCE"]).resolve()
    wheelhouse = Path(os.environ["AUDIODOC_TEST_WHEELHOUSE"]).resolve()

    assert (legacy_source / ".env.example").is_file()
    assert wheelhouse.is_dir()

    monkeypatch.setenv("PIP_NO_INDEX", "1")
    monkeypatch.setenv("PIP_FIND_LINKS", str(wheelhouse))

    for name in (
        "AUDIODOC_AUDIO_KEY",
        "AUDIODOC_DOCUMENT_KEY",
        "WHISPER_API_KEY",
        "DOCUMENT_API_KEY",
        "WHISPER_MODEL_PATH",
        "WHISPER_OFFLINE",
        "BACKEND_TEMP_DIR",
        "AUDIODOC_PORT",
        "AUDIODOC_HOST",
        "PYTHONPATH",
        "FAKE_DOCTOR_FAIL",
        "FAKE_DOCTOR_FAIL_OFFLINE",
    ):
        monkeypatch.delenv(name, raising=False)

    fake_bin, systemctl_log = create_systemctl_stub(tmp_path, active=False)
    extra_env = {
        "PATH": os.pathsep.join((str(fake_bin), os.environ["PATH"])),
        "FAKE_SYSTEMCTL_LOG": str(systemctl_log),
    }

    return legacy_source, extra_env, systemctl_log


def _run_legacy_upgrade(
    release_url: str,
    user_home: Path,
    app_home: Path,
    extra_env: dict[str, str],
):
    """Run a legacy installation upgrade."""
    return run_installer(
        "--upgrade",
        release_url=release_url,
        home=user_home,
        app_home=app_home,
        extra_env=extra_env,
    )


def _assert_successful_upgrade(
    tmp_path: Path,
    legacy_source: Path,
    release_url: str,
    extra_env: dict[str, str],
    systemctl_log: Path,
) -> None:
    """Verify a successful legacy installation upgrade."""
    user_home = tmp_path / "successful-user"
    user_home.mkdir()
    app_home = user_home / "audiodoc"

    source_hashes = _prepare_legacy_installation(legacy_source, app_home)
    preserved_hashes = _preserved_hashes(app_home)
    unit_path, old_unit = _create_legacy_user_unit(user_home, app_home)

    result = _run_legacy_upgrade(release_url, user_home, app_home, extra_env)
    output = result.stdout + result.stderr
    assert result.returncode == 0, output

    legacy_dir = app_home / ".legacy-0.1.0"
    assert legacy_dir.is_dir()
    assert _legacy_source_hashes(legacy_dir) == source_hashes
    assert _preserved_hashes(app_home) == preserved_hashes
    assert (app_home / ".venv" / "bin" / "audiodoc").is_file()

    backup_path = unit_path.with_name("audiodoc.service.bak")
    assert backup_path.read_text(encoding="utf-8") == old_unit

    new_unit = unit_path.read_text(encoding="utf-8")
    assert f'ExecStart="{app_home}/.venv/bin/audiodoc" run' in new_unit
    assert "uvicorn app:app" not in new_unit

    assert systemctl_log.read_text(encoding="utf-8").splitlines() == [
        "--user is-active --quiet audiodoc.service",
        "--user daemon-reload",
    ]

    assert str(legacy_dir) in output
    _assert_doctor_is_green(output)
    _assert_app_imports_from_wheel(app_home)


def _assert_doctor_rollback(
    tmp_path: Path,
    legacy_source: Path,
    release_url: str,
    extra_env: dict[str, str],
    systemctl_log: Path,
) -> None:
    """Verify that a failed doctor restores the legacy installation."""
    user_home = tmp_path / "failed-user"
    user_home.mkdir()
    app_home = user_home / "audiodoc"

    source_hashes = _prepare_legacy_installation(
        legacy_source,
        app_home,
        doctor_failure=True,
    )
    preserved_hashes = _preserved_hashes(app_home)
    unit_path, old_unit = _create_legacy_user_unit(user_home, app_home)
    systemctl_log.write_text("", encoding="utf-8")

    result = _run_legacy_upgrade(release_url, user_home, app_home, extra_env)
    output = result.stdout + result.stderr

    assert result.returncode != 0
    assert "audiodoc doctor failed after the legacy upgrade" in output
    assert any(
        "API keys:" in line and line.startswith("FAIL") for line in output.splitlines()
    )

    assert _legacy_source_hashes(app_home) == source_hashes
    assert _preserved_hashes(app_home) == preserved_hashes
    assert not (app_home / ".legacy-0.1.0").exists()

    assert unit_path.read_text(encoding="utf-8") == old_unit
    backup_path = unit_path.with_name("audiodoc.service.bak")
    assert backup_path.read_text(encoding="utf-8") == old_unit

    assert systemctl_log.read_text(encoding="utf-8").splitlines() == [
        "--user is-active --quiet audiodoc.service",
        "--user daemon-reload",
        "--user daemon-reload",
    ]


def test_v010_legacy_upgrade_preserves_data_and_imports(
    tmp_path: Path,
    local_release_server: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test successful migration of a v0.1.0 installation."""
    legacy_source, extra_env, systemctl_log = _prepare_ci_environment(
        tmp_path,
        monkeypatch,
    )
    _assert_successful_upgrade(
        tmp_path,
        legacy_source,
        local_release_server,
        extra_env,
        systemctl_log,
    )


def test_v010_legacy_upgrade_rolls_back_after_doctor_failure(
    tmp_path: Path,
    local_release_server: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test rollback after the real doctor rejects the upgraded installation."""
    legacy_source, extra_env, systemctl_log = _prepare_ci_environment(
        tmp_path,
        monkeypatch,
    )
    _assert_doctor_rollback(
        tmp_path,
        legacy_source,
        local_release_server,
        extra_env,
        systemctl_log,
    )
