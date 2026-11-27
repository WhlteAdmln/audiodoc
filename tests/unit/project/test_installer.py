# Copyright (c) 2026 Nikolai Zelensky
"""Tests for the POSIX release wheel installer."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, NamedTuple

import pytest

from tests.support.release_server import (
    LocalRelease,
    checksum_line,
    publish,
    serve_release,
    write_manifest,
)
from tests.support.system_commands import (
    install_command,
    install_recording_command,
    path_with,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

PROJECT_ROOT = Path(__file__).resolve().parents[3]
INSTALLER = PROJECT_ROOT / "install.sh"
UPGRADE_FLAG = "--upgrade"
CLEARED_VARIABLES = (
    "AUDIODOC_HOME",
    "AUDIODOC_RELEASE_URL",
    "AUDIODOC_RELEASE_TAG",
    "AUDIODOC_GITHUB_REPOSITORY",
    "GITHUB_TOKEN",
)


class InstallerRun(NamedTuple):
    """The finished installer process and the application home it used."""

    result: subprocess.CompletedProcess[str]
    app_home: Path


def _run_installer(
    *arguments: str,
    home: Path,
    release: LocalRelease | None = None,
    app_home: Path | None = None,
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    shell_path = shutil.which("sh") or "/bin/sh"
    environment = {
        name: value
        for name, value in os.environ.items()
        if name not in CLEARED_VARIABLES
    }
    environment["PIP_NO_INDEX"] = "1"
    environment["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
    environment["HOME"] = str(home)
    if app_home is not None:
        environment["AUDIODOC_HOME"] = str(app_home)
    if release is not None:
        environment["AUDIODOC_RELEASE_URL"] = release.url
        environment["AUDIODOC_RELEASE_TAG"] = "local"
    environment.update(extra_env or {})
    return subprocess.run(  # noqa: S603 - resolved shell runs the local installer.
        [shell_path, str(INSTALLER), *arguments],
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
        env=environment,
        timeout=600 if UPGRADE_FLAG in arguments else 60,
    )


def _rejection(
    result: subprocess.CompletedProcess[str], message: str
) -> tuple[int, bool]:
    return result.returncode, message in result.stderr


def _installed_version(app_home: Path) -> str:
    pattern = "lib/python*/site-packages/audiodoc-*.dist-info/METADATA"
    versions = [
        line.removeprefix("Version: ")
        for metadata in (app_home / ".venv").glob(pattern)
        for line in metadata.read_text(encoding="utf-8").splitlines()
        if line.startswith("Version: ")
    ]
    return ",".join(versions)


def _recorded_calls(app_home: Path) -> list[list[str]]:
    lines = (app_home / "calls.jsonl").read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines]


def _existing_files(app_home: Path, names: list[str]) -> list[str]:
    return [name for name in names if (app_home / name).is_file()]


def _fake_installation(app_home: Path) -> None:
    (app_home / ".venv" / "bin").mkdir(parents=True)
    (app_home / ".env").write_text("CUSTOM_SETTING=keep\n", encoding="utf-8")
    python = app_home / ".venv" / "bin" / "python"
    python.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    python.chmod(0o755)


def _seed_application_data(app_home: Path) -> dict[Path, bytes]:
    files = {
        app_home / ".env": b"CUSTOM_SETTING=keep-me\n",
        app_home / "models" / "keep.bin": b"model-data",
        app_home / "tmp" / "keep.tmp": b"temporary-data",
    }
    for path, content in files.items():
        path.parent.mkdir(exist_ok=True)
        path.write_bytes(content)
    return files


@pytest.fixture(name="user_home")
def fixture_user_home(tmp_path: Path) -> Path:
    """Provide an empty home directory for the installing user."""
    home = tmp_path / "user"
    home.mkdir()
    return home


@pytest.fixture(name="release")
def fixture_release(tmp_path: Path) -> Iterator[LocalRelease]:
    """Serve a valid release with version 1.2.3 over local HTTP."""
    directory = tmp_path / "release"
    directory.mkdir()
    publish(directory)
    with serve_release(directory) as release:
        yield release


@pytest.fixture(name="default_install")
def fixture_default_install(user_home: Path, release: LocalRelease) -> InstallerRun:
    """Install with default options into the default application home."""
    result = _run_installer(home=user_home, release=release)
    return InstallerRun(result, user_home / "audiodoc")


@pytest.fixture(name="initial_install")
def fixture_initial_install(user_home: Path, release: LocalRelease) -> InstallerRun:
    """Install version 1.2.3 with a user service and publish version 2.0.0."""
    result = _run_installer("--no-model", "--systemd", home=user_home, release=release)
    publish(release.directory, version="2.0.0")
    return InstallerRun(result, user_home / "audiodoc")


@pytest.fixture(name="inactive_systemctl")
def fixture_inactive_systemctl(tmp_path: Path) -> tuple[Path, Path]:
    """Provide a systemctl that reports an inactive service and logs calls."""
    log_path = tmp_path / "systemctl.log"
    bin_dir = tmp_path / "bin"
    install_recording_command(bin_dir, "systemctl", log_path, exit_code=3)
    return bin_dir, log_path


def test_installer_help_lists_every_option(user_home: Path) -> None:
    options = [
        "--model",
        "--device",
        "--compute-type",
        "--host",
        "--port",
        "--no-model",
        "--systemd",
        "--os-packages",
        "--upgrade",
    ]

    result = _run_installer("--help", home=user_home)

    missing = [option for option in options if option not in result.stdout]
    expected: tuple[int, list[str]] = (0, [])
    assert (result.returncode, missing) == expected, "help must list every option"


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        (["--port", "65536"], "Port must be an integer between 1 and 65535."),
        (["--port", "0"], "Port must be an integer between 1 and 65535."),
        (["--port", "80;id"], "Port must be an integer between 1 and 65535."),
        (["--port", "1e3"], "Port must be an integer between 1 and 65535."),
        (["--device", "gpu"], "--device must be cpu or cuda."),
        (["--device", "cuda$(id)"], "--device must be cpu or cuda."),
        (["--model", "made-up-model"], "Unsupported Whisper model name"),
        (["--model", "../small"], "Unsupported Whisper model name"),
        (["--compute-type", "int8;id"], "Invalid compute type"),
        (["--host", "0.0.0.0;touch unsafe"], "Invalid host address"),
        (["--host", "127.0.0.1 --reload"], "Invalid host address"),
        (["--host", "-0.0.0.0"], "Invalid value for --host"),
        (["--model", ""], "Invalid value for --model"),
        (["--port"], "Option --port requires a value."),
        (["--sudo"], "Unknown argument: --sudo"),
        (["--upgrade", "--os-packages"], "--upgrade cannot be combined"),
    ],
)
def test_installer_rejects_unsafe_option_before_installation(
    user_home: Path, arguments: list[str], message: str
) -> None:
    result = _run_installer(*arguments, home=user_home)

    expected = (1, True)
    assert _rejection(result, message) == expected, result.stderr


@pytest.mark.parametrize(
    "template",
    ["127.0.0.1;touch {marker}", "$(touch {marker})", "`touch {marker}`"],
)
def test_installer_does_not_run_a_command_injected_through_the_host(
    tmp_path: Path, user_home: Path, template: str
) -> None:
    marker = tmp_path / "внедрённый маркер"

    _run_installer("--host", template.format(marker=marker), home=user_home)

    assert marker.exists() is False, "a host value must never run as a command"


@pytest.mark.parametrize(
    ("repository", "message"),
    [
        ("owner/name/extra", "Invalid GitHub repository"),
        ("owner/na me", "Invalid GitHub repository"),
        ("/name", "Invalid GitHub repository"),
        ("owner/", "Invalid GitHub repository"),
        ("owner/name;id", "Invalid GitHub repository"),
        ("owner", "must have owner/name format"),
    ],
)
def test_installer_rejects_unsafe_github_repository(
    user_home: Path, repository: str, message: str
) -> None:
    result = _run_installer(
        home=user_home, extra_env={"AUDIODOC_GITHUB_REPOSITORY": repository}
    )

    expected = (1, True)
    assert _rejection(result, message) == expected, result.stderr


@pytest.mark.parametrize("suffix", ["", "/", "//"])
def test_installer_refuses_the_user_home_as_installation_directory(
    user_home: Path, suffix: str
) -> None:
    app_home = Path(f"{user_home}{suffix}")

    result = _run_installer("--no-model", home=user_home, app_home=app_home)

    expected = (1, True)
    message = "Refusing unsafe installation directory"
    assert _rejection(result, message) == expected, result.stderr


def test_installer_refuses_the_root_as_installation_directory(
    user_home: Path,
) -> None:
    root = Path("/")

    result = _run_installer("--no-model", home=user_home, app_home=root)

    expected = (1, True)
    message = "Refusing unsafe installation directory: /"
    assert _rejection(result, message) == expected, result.stderr


def test_installer_keeps_data_of_an_existing_home(
    user_home: Path, release: LocalRelease
) -> None:
    app_home = user_home / "audiodoc"
    app_home.mkdir()
    marker = app_home / "keep.txt"
    marker.write_text("existing data", encoding="utf-8")

    result = _run_installer("--no-model", home=user_home, release=release)

    observed = (
        *_rejection(result, "Installation directory already exists"),
        marker.read_text(encoding="utf-8"),
    )
    expected = (1, True, "existing data")
    assert observed == expected, "an existing home must be left untouched"


def test_installer_refuses_a_symlink_as_installation_directory(
    tmp_path: Path, user_home: Path, release: LocalRelease
) -> None:
    target = tmp_path / "elsewhere"
    target.mkdir()
    app_home = user_home / "audiodoc"
    app_home.symlink_to(target)

    result = _run_installer(
        "--no-model", home=user_home, release=release, app_home=app_home
    )

    observed = (
        *_rejection(result, "Installation directory already exists"),
        sorted(path.name for path in target.iterdir()),
    )
    expected: tuple[int, bool, list[str]] = (1, True, [])
    assert observed == expected, "a symlinked home must not be installed into"


def _remove_home(app_home: Path) -> None:
    shutil.rmtree(app_home)


def _symlink_env(app_home: Path) -> None:
    real_env = app_home.parent / "real.env"
    (app_home / ".env").rename(real_env)
    (app_home / ".env").symlink_to(real_env)


def _remove_venv(app_home: Path) -> None:
    shutil.rmtree(app_home / ".venv")


def _make_python_non_executable(app_home: Path) -> None:
    (app_home / ".venv" / "bin" / "python").chmod(0o644)


def _leave_staged_venv(app_home: Path) -> None:
    (app_home / ".venv.new").mkdir()


def _link_backup_venv(app_home: Path) -> None:
    (app_home / ".venv.prev").symlink_to(app_home.parent)


def _symlink_home(app_home: Path) -> None:
    real_home = app_home.parent / "real-home"
    app_home.rename(real_home)
    app_home.symlink_to(real_home)


@pytest.mark.parametrize(
    ("damage", "message"),
    [
        (_remove_home, "Upgrade requires an existing installation directory"),
        (_symlink_home, "Upgrade requires an existing installation directory"),
        (_symlink_env, "Upgrade requires an existing regular .env file."),
        (_remove_venv, "Upgrade requires an existing .venv directory."),
        (_make_python_non_executable, "has no executable Python interpreter"),
        (_leave_staged_venv, "Refusing to overwrite stale upgrade directory"),
        (_link_backup_venv, "Refusing to overwrite stale upgrade backup"),
    ],
)
def test_upgrade_refuses_an_unsafe_existing_installation(
    user_home: Path, damage: Callable[[Path], None], message: str
) -> None:
    app_home = user_home / "audiodoc"
    _fake_installation(app_home)
    damage(app_home)

    result = _run_installer(UPGRADE_FLAG, home=user_home)

    expected = (1, True)
    assert _rejection(result, message) == expected, result.stderr


def test_upgrade_refuses_an_active_user_service(
    tmp_path: Path, user_home: Path
) -> None:
    app_home = user_home / "audiodoc"
    _fake_installation(app_home)
    bin_dir = tmp_path / "bin"
    install_command(bin_dir, "systemctl", "exit 0\n")

    result = _run_installer(
        UPGRADE_FLAG, home=user_home, extra_env={"PATH": path_with(bin_dir)}
    )

    observed = (
        *_rejection(result, "user service is active"),
        sorted(path.name for path in app_home.iterdir()),
    )
    expected = (1, True, [".env", ".venv"])
    assert observed == expected, "an active service must block the upgrade"


def _corrupt_wheel_digest(directory: Path) -> list[str]:
    wheel = next(directory.glob("audiodoc-*.whl"))
    return ["0" * 64 + f"  {wheel.name}", checksum_line(directory / "constraints.txt")]


def _corrupt_constraints_digest(directory: Path) -> list[str]:
    wheel = next(directory.glob("audiodoc-*.whl"))
    return [checksum_line(wheel), "f" * 64 + "  constraints.txt"]


def _list_two_wheels(directory: Path) -> list[str]:
    wheel = next(directory.glob("audiodoc-*.whl"))
    return [
        checksum_line(wheel),
        "a" * 64 + "  audiodoc-9.9.9-py3-none-any.whl",
        checksum_line(directory / "constraints.txt"),
    ]


def _duplicate_wheel(directory: Path) -> list[str]:
    wheel = next(directory.glob("audiodoc-*.whl"))
    return [
        checksum_line(wheel),
        checksum_line(wheel),
        checksum_line(directory / "constraints.txt"),
    ]


def _omit_constraints(directory: Path) -> list[str]:
    return [checksum_line(next(directory.glob("audiodoc-*.whl")))]


def _traverse_wheel_path(directory: Path) -> list[str]:
    wheel = next(directory.glob("audiodoc-*.whl"))
    digest = checksum_line(wheel).split()[0]
    return [
        f"{digest}  ../{wheel.name}",
        checksum_line(directory / "constraints.txt"),
    ]


def _list_missing_wheel(directory: Path) -> list[str]:
    return [
        "b" * 64 + "  audiodoc-7.0.0-py3-none-any.whl",
        checksum_line(directory / "constraints.txt"),
    ]


def _empty_manifest(_directory: Path) -> list[str]:
    return []


@pytest.mark.parametrize(
    ("manifest", "message"),
    [
        (_corrupt_wheel_digest, "Release SHA-256 verification failed."),
        (_corrupt_constraints_digest, "Release SHA-256 verification failed."),
        (_list_two_wheels, "Release SHA256SUMS is invalid."),
        (_duplicate_wheel, "Release SHA256SUMS is invalid."),
        (_omit_constraints, "Release SHA256SUMS is invalid."),
        (_traverse_wheel_path, "has no wheel asset"),
        (_empty_manifest, "has no wheel asset"),
        (_list_missing_wheel, "Could not download release asset"),
    ],
)
def test_installer_rejects_an_untrusted_release_and_leaves_no_home(
    user_home: Path,
    release: LocalRelease,
    manifest: Callable[[Path], list[str]],
    message: str,
) -> None:
    write_manifest(release.directory, manifest(release.directory))

    result = _run_installer("--no-model", home=user_home, release=release)

    observed = (*_rejection(result, message), (user_home / "audiodoc").exists())
    expected = (1, True, False)
    assert observed == expected, result.stderr


@pytest.mark.parametrize("tag", ["v1;id", "../v1", "v1 v2", "v1\nv2"])
def test_installer_rejects_an_unsafe_release_tag(
    user_home: Path, release: LocalRelease, tag: str
) -> None:
    result = _run_installer(
        "--no-model",
        home=user_home,
        release=release,
        extra_env={"AUDIODOC_RELEASE_TAG": tag},
    )

    expected = (1, True)
    assert _rejection(result, "Invalid release tag") == expected, result.stderr


def test_installer_passes_options_to_init_and_installs_the_user_service(
    user_home: Path, release: LocalRelease
) -> None:
    app_home = user_home / "custom audiodoc home"
    options = [
        "--model",
        "tiny",
        "--device",
        "cuda",
        "--compute-type",
        "int8",
        "--host",
        "127.0.0.2",
        "--port",
        "8123",
    ]

    result = _run_installer(
        "--no-model",
        *options,
        "--systemd",
        home=user_home,
        release=release,
        app_home=app_home,
    )

    files = [".venv/bin/audiodoc", ".env", "service-installed"]
    observed = {
        "returncode": result.returncode,
        "files": _existing_files(app_home, files),
        "calls": _recorded_calls(app_home),
    }
    expected = {
        "returncode": 0,
        "files": files,
        "calls": [["init", *options], ["doctor"], ["service", "install", "--user"]],
    }
    assert observed == expected, result.stdout + result.stderr


def test_installer_downloads_the_model_and_configures_offline_use(
    default_install: InstallerRun,
) -> None:
    app_home = default_install.app_home
    model_path = app_home / "models" / "small"
    env_lines = (app_home / ".env").read_text(encoding="utf-8").splitlines()

    observed = {
        "returncode": default_install.result.returncode,
        "model": _existing_files(model_path, ["config.json", "model.bin"]),
        "settings": [line for line in env_lines if line.startswith("WHISPER_")],
        "calls": _recorded_calls(app_home)[1:],
    }
    expected = {
        "returncode": 0,
        "model": ["config.json", "model.bin"],
        "settings": [f'WHISPER_MODEL_PATH="{model_path}"', "WHISPER_OFFLINE=true"],
        "calls": [
            ["model", "download", "--name", "small", "--dir", str(model_path)],
            ["doctor"],
        ],
    }
    assert observed == expected, default_install.result.stderr


def test_installer_creates_a_private_application_directory(
    default_install: InstallerRun,
) -> None:
    mode = default_install.app_home.stat().st_mode & 0o777

    expected_mode = 0o700
    assert mode == expected_mode, "the application home must be private to the user"


def _native_package_environment(tmp_path: Path) -> tuple[dict[str, str], Path, Path]:
    bin_dir = tmp_path / "bin"
    marker = tmp_path / "native-installed"
    sudo_log = tmp_path / "sudo.log"
    install_command(bin_dir, "apt-get", "exit 0\n")
    install_command(
        bin_dir,
        "sudo",
        'printf "%s\\n" "$*" >> "$FAKE_SUDO_LOG"\ntouch "$FAKE_INSTALL_MARKER"\n',
    )
    environment = {
        "PATH": path_with(bin_dir),
        "FAKE_DOCTOR_REQUIRES_NATIVE": "1",
        "FAKE_INSTALL_MARKER": str(marker),
        "FAKE_SUDO_LOG": str(sudo_log),
    }
    return environment, marker, sudo_log


def test_installer_runs_the_native_package_command_when_opted_in(
    tmp_path: Path, user_home: Path, release: LocalRelease
) -> None:
    environment, marker, sudo_log = _native_package_environment(tmp_path)

    result = _run_installer(
        "--no-model",
        "--os-packages",
        home=user_home,
        release=release,
        extra_env=environment,
    )

    observed = (
        result.returncode,
        marker.is_file(),
        sudo_log.read_text(encoding="utf-8") if sudo_log.exists() else "",
    )
    expected = (0, True, "apt install test-native-package\n")
    assert observed == expected, result.stdout + result.stderr


def test_installer_runs_no_native_package_command_without_opt_in(
    tmp_path: Path, user_home: Path, release: LocalRelease
) -> None:
    environment, marker, sudo_log = _native_package_environment(tmp_path)

    result = _run_installer(
        "--no-model", home=user_home, release=release, extra_env=environment
    )

    observed = (
        *_rejection(result, "audiodoc doctor failed"),
        marker.exists(),
        sudo_log.exists(),
        (user_home / "audiodoc").exists(),
    )
    expected = (1, True, False, False, False)
    assert observed == expected, "no sudo call and no partial installation"


def test_upgrade_replaces_the_environment_and_preserves_application_data(
    initial_install: InstallerRun,
    inactive_systemctl: tuple[Path, Path],
    user_home: Path,
    release: LocalRelease,
) -> None:
    app_home = initial_install.app_home
    preserved = _seed_application_data(app_home)
    old_marker = app_home / ".venv" / "old-environment-marker"
    old_marker.write_text("old", encoding="utf-8")
    bin_dir, systemctl_log = inactive_systemctl

    result = _run_installer(
        UPGRADE_FLAG,
        home=user_home,
        release=release,
        extra_env={"PATH": path_with(bin_dir)},
    )

    calls = _recorded_calls(app_home)
    restart_hint = "systemctl --user restart audiodoc.service"
    observed = {
        "returncode": result.returncode,
        "preserved": {path: path.read_bytes() for path in preserved} == preserved,
        "service unit kept": (app_home / "service-installed").is_file(),
        "old environment left": old_marker.exists(),
        "version": _installed_version(app_home),
        "leftovers": [
            name for name in (".venv.new", ".venv.prev") if (app_home / name).exists()
        ],
        "restart hint": restart_hint in result.stdout,
        "last call": calls[-1],
        "service installs": calls.count(["service", "install", "--user"]),
        "systemctl": systemctl_log.read_text(encoding="utf-8").splitlines(),
    }
    expected = {
        "returncode": 0,
        "preserved": True,
        "service unit kept": True,
        "old environment left": False,
        "version": "2.0.0",
        "leftovers": [],
        "restart hint": True,
        "last call": ["doctor", "--offline"],
        "service installs": 1,
        "systemctl": [
            "--user is-active --quiet audiodoc.service",
            "--user is-active --quiet audiodoc.service",
        ],
    }
    assert observed == expected, result.stdout + result.stderr


def _files_naming(directory: Path, text: str) -> list[str]:
    needle = os.fsencode(text)
    return [
        str(path.relative_to(directory))
        for path in sorted(directory.rglob("*"))
        if path.is_file() and not path.is_symlink() and needle in path.read_bytes()
    ]


def test_upgrade_leaves_no_staged_path_in_the_environment(
    initial_install: InstallerRun,
    inactive_systemctl: tuple[Path, Path],
    user_home: Path,
    release: LocalRelease,
) -> None:
    app_home = initial_install.app_home
    bin_dir, _systemctl_log = inactive_systemctl

    result = _run_installer(
        UPGRADE_FLAG,
        home=user_home,
        release=release,
        extra_env={"PATH": path_with(bin_dir)},
    )

    observed = (result.returncode, _files_naming(app_home / ".venv", ".venv.new"))
    expected = (0, [])
    assert observed == expected, result.stdout + result.stderr


def test_upgraded_command_runs_the_offline_doctor(
    initial_install: InstallerRun,
    inactive_systemctl: tuple[Path, Path],
    user_home: Path,
    release: LocalRelease,
) -> None:
    app_home = initial_install.app_home
    bin_dir, _systemctl_log = inactive_systemctl
    _run_installer(
        UPGRADE_FLAG,
        home=user_home,
        release=release,
        extra_env={"PATH": path_with(bin_dir)},
    )

    doctor = subprocess.run(  # noqa: S603 - runs the upgraded local command.
        [str(app_home / ".venv" / "bin" / "audiodoc"), "doctor", "--offline"],
        check=False,
        capture_output=True,
        text=True,
        env={**os.environ, "AUDIODOC_HOME": str(app_home)},
        timeout=60,
    )

    observed = (doctor.returncode, doctor.stdout)
    expected = (0, "doctor OK\n")
    assert observed == expected, doctor.stderr


def test_upgrade_rolls_back_when_the_offline_doctor_fails(
    initial_install: InstallerRun,
    inactive_systemctl: tuple[Path, Path],
    user_home: Path,
    release: LocalRelease,
) -> None:
    app_home = initial_install.app_home
    old_marker = app_home / ".venv" / "old-environment-marker"
    old_marker.write_text("old", encoding="utf-8")
    bin_dir, _systemctl_log = inactive_systemctl

    result = _run_installer(
        UPGRADE_FLAG,
        home=user_home,
        release=release,
        extra_env={"PATH": path_with(bin_dir), "FAKE_DOCTOR_FAIL_OFFLINE": "1"},
    )

    observed = {
        "rejection": _rejection(result, "doctor --offline failed"),
        "old environment": old_marker.read_text(encoding="utf-8"),
        "version": _installed_version(app_home),
        "leftovers": [
            name for name in (".venv.new", ".venv.prev") if (app_home / name).exists()
        ],
    }
    expected = {
        "rejection": (1, True),
        "old environment": "old",
        "version": "1.2.3",
        "leftovers": [],
    }
    assert observed == expected, result.stdout + result.stderr


def _refuse_to_move_the_staged_venv(bin_dir: Path) -> None:
    real_mv = shutil.which("mv") or "/bin/mv"
    body = f'case "$1" in\n*/.venv.new) exit 1 ;;\nesac\nexec "{real_mv}" "$@"\n'
    install_command(bin_dir, "mv", body)


def test_upgrade_restores_the_previous_environment_when_the_switch_fails(
    initial_install: InstallerRun,
    inactive_systemctl: tuple[Path, Path],
    user_home: Path,
    release: LocalRelease,
) -> None:
    app_home = initial_install.app_home
    old_marker = app_home / ".venv" / "previous-environment-marker"
    old_marker.write_text("vorherige Umgebung", encoding="utf-8")
    bin_dir, _systemctl_log = inactive_systemctl
    _refuse_to_move_the_staged_venv(bin_dir)

    result = _run_installer(
        UPGRADE_FLAG,
        home=user_home,
        release=release,
        extra_env={"PATH": path_with(bin_dir)},
    )

    observed = {
        "rejection": _rejection(
            result, "Could not activate the staged virtual environment."
        ),
        "old environment": old_marker.read_text(encoding="utf-8"),
        "version": _installed_version(app_home),
        "leftovers": [
            name for name in (".venv.new", ".venv.prev") if (app_home / name).exists()
        ],
    }
    expected = {
        "rejection": (1, True),
        "old environment": "vorherige Umgebung",
        "version": "1.2.3",
        "leftovers": [],
    }
    assert observed == expected, result.stdout + result.stderr
