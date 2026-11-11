# Copyright (c) 2026 Nikolai Zelensky
"""Tests for the POSIX release wheel installer."""

import base64
import csv
import hashlib
import io
import json
import os
import shutil
import subprocess
import zipfile
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
INSTALLER = PROJECT_ROOT / "install.sh"

FAKE_CLI_SOURCE = """
import json
import os
import sys
from pathlib import Path


def main():
    args = sys.argv[1:]
    home = Path(os.environ["AUDIODOC_HOME"])
    home.mkdir(parents=True, exist_ok=True)
    with (home / "calls.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(args) + "\\n")

    if args[0] == "init":
        env_path = home / ".env"
        env_path.write_text(
            "AUDIODOC_AUDIO_KEY=test-audio\\n"
            "AUDIODOC_DOCUMENT_KEY=test-document\\n"
            "WHISPER_MODEL_PATH=\\n"
            "WHISPER_OFFLINE=false\\n",
            encoding="utf-8",
        )
        env_path.chmod(0o600)
        return 0

    if args[0] == "model":
        directory = Path(args[args.index("--dir") + 1])
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "config.json").write_text("{}", encoding="utf-8")
        (directory / "model.bin").write_bytes(b"test-model")
        print("Model downloaded to: " + str(directory))
        return 0

    if args[0] == "doctor":
        marker = os.environ.get("FAKE_INSTALL_MARKER")
        if (
            os.environ.get("FAKE_DOCTOR_REQUIRES_NATIVE") == "1"
            and (marker is None or not Path(marker).is_file())
        ):
            print("FAIL Tesseract: executable not found.")
            print("Install missing native tools with one of:")
            print("  Debian/Ubuntu: sudo apt install test-native-package")
            print("  Fedora/RHEL: sudo dnf install test-native-package")
            print("  Arch Linux: sudo pacman -S test-native-package")
            return 1
        if "--offline" in args and os.environ.get("FAKE_DOCTOR_FAIL_OFFLINE") == "1":
            print("FAIL Whisper model: model is not cached.")
            return 1
        print("doctor OK")
        return 0

    if args[:2] == ["service", "install"]:
        (home / "service-installed").write_text("ok", encoding="utf-8")
        return 0

    return 2
"""


def run_installer(
    *arguments: str,
    release_url: str | None = None,
    home: Path | None = None,
    app_home: Path | None = None,
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run the installer with an isolated environment."""
    shell_path = shutil.which("sh")
    assert shell_path is not None, "A POSIX shell is required"

    environment = os.environ.copy()
    environment["PIP_NO_INDEX"] = "1"
    environment["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
    environment.pop("AUDIODOC_HOME", None)
    environment.pop("AUDIODOC_RELEASE_URL", None)
    environment.pop("AUDIODOC_RELEASE_TAG", None)
    environment.pop("AUDIODOC_GITHUB_REPOSITORY", None)
    environment.pop("GITHUB_TOKEN", None)

    if home is not None:
        environment["HOME"] = str(home)
    if app_home is not None:
        environment["AUDIODOC_HOME"] = str(app_home)
    if release_url is not None:
        environment["AUDIODOC_RELEASE_URL"] = release_url
        environment["AUDIODOC_RELEASE_TAG"] = "local"
    if extra_env is not None:
        environment.update(extra_env)

    return subprocess.run(  # noqa: S603 - resolved shell runs the local installer.
        [shell_path, str(INSTALLER), *arguments],
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
        env=environment,
        timeout=60,
    )


def create_test_wheel(release_dir: Path) -> Path:
    """Build a minimal wheel containing an isolated fake audiodoc CLI."""
    version = "1.2.3"
    distribution = f"audiodoc-{version}.dist-info"
    wheel_name = f"audiodoc-{version}-py3-none-any.whl"

    files = {
        "audiodoc/__init__.py": b"",
        "audiodoc/__main__.py": (
            b"from audiodoc.cli import main\nraise SystemExit(main())\n"
        ),
        "audiodoc/cli.py": FAKE_CLI_SOURCE.encode("utf-8"),
        f"{distribution}/METADATA": (
            f"Metadata-Version: 2.1\n"
            f"Name: audiodoc\n"
            f"Version: {version}\n"
            "Requires-Python: >=3.11\n\n"
        ).encode(),
        f"{distribution}/WHEEL": (
            b"Wheel-Version: 1.0\n"
            b"Generator: audiodoc-installer-test\n"
            b"Root-Is-Purelib: true\n"
            b"Tag: py3-none-any\n"
        ),
        f"{distribution}/entry_points.txt": (
            b"[console_scripts]\naudiodoc = audiodoc.cli:main\n"
        ),
    }

    rows = []
    for name, content in files.items():
        digest = (
            base64.urlsafe_b64encode(hashlib.sha256(content).digest())
            .rstrip(b"=")
            .decode("ascii")
        )
        rows.append((name, f"sha256={digest}", str(len(content))))

    record_name = f"{distribution}/RECORD"
    record_stream = io.StringIO()
    csv.writer(record_stream, lineterminator="\n").writerows(
        [*rows, (record_name, "", "")]
    )
    files[record_name] = record_stream.getvalue().encode("utf-8")

    wheel_path = release_dir / wheel_name
    with zipfile.ZipFile(wheel_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr(name, content)

    return wheel_path


def write_checksums(
    release_dir: Path,
    wheel_path: Path,
    *,
    corrupt: bool = False,
) -> None:
    """Write a release checksum manifest."""
    wheel_digest = hashlib.sha256(wheel_path.read_bytes()).hexdigest()
    if corrupt:
        wheel_digest = "0" * 64

    archive_digest = hashlib.sha256(b"release-archive").hexdigest()
    constraints_digest = hashlib.sha256(
        (release_dir / "constraints.txt").read_bytes()
    ).hexdigest()

    manifest = (
        f"{archive_digest}  audiodoc-1.2.3.zip\n"
        f"{wheel_digest}  {wheel_path.name}\n"
        f"{constraints_digest}  constraints.txt\n"
    )
    (release_dir / "SHA256SUMS").write_text(manifest, encoding="utf-8")


@pytest.fixture
def local_release(tmp_path: Path) -> tuple[str, Path]:
    """Provide release assets through a local file URL."""
    release_dir = tmp_path / "release"
    release_dir.mkdir()

    wheel_path = create_test_wheel(release_dir)
    (release_dir / "constraints.txt").write_text("", encoding="utf-8")
    write_checksums(release_dir, wheel_path)

    return release_dir.as_uri(), release_dir


def test_installer_help_succeeds() -> None:
    result = run_installer("--help")

    assert result.returncode == 0
    assert "--model" in result.stdout
    assert "--device" in result.stdout
    assert "--compute-type" in result.stdout
    assert "--systemd" in result.stdout
    assert "--no-model" in result.stdout
    assert "--os-packages" in result.stdout


def test_installer_rejects_invalid_port_before_installation() -> None:
    result = run_installer("--port", "65536")

    assert result.returncode != 0
    assert "Port must be an integer" in result.stderr


def test_installer_rejects_unsupported_device_before_installation() -> None:
    result = run_installer("--device", "gpu")

    assert result.returncode != 0
    assert "--device must be cpu or cuda" in result.stderr


def test_installer_rejects_unknown_model_before_installation() -> None:
    result = run_installer("--model", "made-up-model")

    assert result.returncode != 0
    assert "Unsupported Whisper model name" in result.stderr


def test_installer_rejects_invalid_host_before_installation() -> None:
    result = run_installer("--host", "0.0.0.0;touch /tmp/unsafe")

    assert result.returncode != 0
    assert "Invalid host address" in result.stderr


def test_installer_installs_wheel_and_initializes_application(
    tmp_path: Path,
    local_release: tuple[str, Path],
) -> None:
    release_url, _release_dir = local_release
    user_home = tmp_path / "user"
    user_home.mkdir()
    app_home = tmp_path / "custom audiodoc home"

    result = run_installer(
        "--no-model",
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
        "--systemd",
        release_url=release_url,
        home=user_home,
        app_home=app_home,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert (app_home / ".venv" / "bin" / "audiodoc").is_file()
    assert (app_home / ".env").is_file()
    assert (app_home / "service-installed").is_file()

    calls = [
        json.loads(line)
        for line in (app_home / "calls.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert calls == [
        [
            "init",
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
        ],
        ["doctor"],
        ["service", "install", "--user"],
    ]


def test_installer_downloads_model_and_configures_offline_path(
    tmp_path: Path,
    local_release: tuple[str, Path],
) -> None:
    release_url, _release_dir = local_release
    user_home = tmp_path / "user"
    user_home.mkdir()
    app_home = user_home / "audiodoc"

    result = run_installer(
        release_url=release_url,
        home=user_home,
    )

    assert result.returncode == 0, result.stdout + result.stderr

    model_path = app_home / "models" / "small"
    assert (model_path / "config.json").is_file()
    assert (model_path / "model.bin").is_file()

    env_content = (app_home / ".env").read_text(encoding="utf-8")
    assert f'WHISPER_MODEL_PATH="{model_path}"' in env_content
    assert "WHISPER_OFFLINE=true" in env_content

    calls = [
        json.loads(line)
        for line in (app_home / "calls.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert calls[0] == [
        "init",
        "--model",
        "small",
        "--device",
        "cpu",
        "--compute-type",
        "int8",
        "--host",
        "127.0.0.1",
        "--port",
        "8000",
    ]
    assert calls[1] == [
        "model",
        "download",
        "--name",
        "small",
        "--dir",
        str(model_path),
    ]
    assert calls[2] == ["doctor"]


def test_os_packages_are_installed_only_when_opted_in(
    tmp_path: Path,
    local_release: tuple[str, Path],
) -> None:
    release_url, _release_dir = local_release
    user_home = tmp_path / "user"
    user_home.mkdir()
    app_home = tmp_path / "audiodoc"
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()

    marker = tmp_path / "native-installed"
    sudo_log = tmp_path / "sudo.log"

    (fake_bin / "apt-get").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    (fake_bin / "sudo").write_text(
        "#!/bin/sh\n"
        'printf "%s\\n" "$*" >> "$FAKE_SUDO_LOG"\n'
        'touch "$FAKE_INSTALL_MARKER"\n',
        encoding="utf-8",
    )
    (fake_bin / "apt-get").chmod(0o755)
    (fake_bin / "sudo").chmod(0o755)

    extra_env = {
        "PATH": str(fake_bin) + os.pathsep + os.environ["PATH"],
        "FAKE_DOCTOR_REQUIRES_NATIVE": "1",
        "FAKE_INSTALL_MARKER": str(marker),
        "FAKE_SUDO_LOG": str(sudo_log),
    }

    result = run_installer(
        "--no-model",
        "--os-packages",
        release_url=release_url,
        home=user_home,
        app_home=app_home,
        extra_env=extra_env,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert marker.is_file()
    assert sudo_log.read_text(encoding="utf-8").strip() == (
        "apt install test-native-package"
    )


def test_installer_does_not_install_os_packages_without_opt_in(
    tmp_path: Path,
    local_release: tuple[str, Path],
) -> None:
    release_url, _release_dir = local_release
    user_home = tmp_path / "user"
    user_home.mkdir()
    app_home = tmp_path / "audiodoc"
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()

    sudo_log = tmp_path / "sudo.log"
    marker = tmp_path / "native-installed"

    (fake_bin / "apt-get").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    (fake_bin / "sudo").write_text(
        "#!/bin/sh\n"
        'printf "%s\\n" "$*" >> "$FAKE_SUDO_LOG"\n'
        'touch "$FAKE_INSTALL_MARKER"\n',
        encoding="utf-8",
    )
    (fake_bin / "apt-get").chmod(0o755)
    (fake_bin / "sudo").chmod(0o755)

    result = run_installer(
        "--no-model",
        release_url=release_url,
        home=user_home,
        app_home=app_home,
        extra_env={
            "PATH": str(fake_bin) + os.pathsep + os.environ["PATH"],
            "FAKE_DOCTOR_REQUIRES_NATIVE": "1",
            "FAKE_INSTALL_MARKER": str(marker),
            "FAKE_SUDO_LOG": str(sudo_log),
        },
    )

    assert result.returncode != 0
    assert "audiodoc doctor failed" in result.stderr
    assert not marker.exists()
    assert not sudo_log.exists()
    assert not app_home.exists()


def test_installer_rejects_checksum_mismatch(
    tmp_path: Path,
    local_release: tuple[str, Path],
) -> None:
    release_url, release_dir = local_release
    wheel_path = next(release_dir.glob("audiodoc-*.whl"))
    write_checksums(release_dir, wheel_path, corrupt=True)

    user_home = tmp_path / "user"
    user_home.mkdir()
    app_home = tmp_path / "audiodoc"

    result = run_installer(
        "--no-model",
        release_url=release_url,
        home=user_home,
        app_home=app_home,
    )

    assert result.returncode != 0
    assert "SHA-256 verification failed" in result.stderr
    assert not app_home.exists()


def test_installer_refuses_existing_home(
    tmp_path: Path,
    local_release: tuple[str, Path],
) -> None:
    release_url, _release_dir = local_release
    user_home = tmp_path / "user"
    user_home.mkdir()
    app_home = user_home / "audiodoc"
    app_home.mkdir()

    marker = app_home / "keep.txt"
    marker.write_text("existing data", encoding="utf-8")

    result = run_installer(
        "--no-model",
        release_url=release_url,
        home=user_home,
        app_home=app_home,
    )

    assert result.returncode != 0
    assert "Installation directory already exists" in result.stderr
    assert marker.read_text(encoding="utf-8") == "existing data"


def test_installer_upgrades_existing_environment_and_preserves_application_data(
    tmp_path: Path,
    local_release: tuple[str, Path],
) -> None:
    release_url, _release_dir = local_release
    user_home = tmp_path / "user"
    user_home.mkdir()
    app_home = user_home / "audiodoc"

    initial = run_installer(
        "--no-model",
        "--systemd",
        release_url=release_url,
        home=user_home,
    )
    assert initial.returncode == 0, initial.stdout + initial.stderr

    env_path = app_home / ".env"
    env_path.write_text("CUSTOM_SETTING=keep-me\n", encoding="utf-8")
    models_dir = app_home / "models"
    models_dir.mkdir()
    (models_dir / "keep.bin").write_bytes(b"model-data")
    tmp_dir = app_home / "tmp"
    tmp_dir.mkdir()
    (tmp_dir / "keep.tmp").write_text("temporary-data", encoding="utf-8")
    old_marker = app_home / ".venv" / "old-environment-marker"
    old_marker.write_text("old", encoding="utf-8")

    result = run_installer(
        "--upgrade",
        release_url=release_url,
        home=user_home,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert env_path.read_text(encoding="utf-8") == "CUSTOM_SETTING=keep-me\n"
    assert (models_dir / "keep.bin").read_bytes() == b"model-data"
    assert (tmp_dir / "keep.tmp").read_text(encoding="utf-8") == "temporary-data"
    assert (app_home / "service-installed").read_text(encoding="utf-8") == "ok"
    assert not old_marker.exists()
    assert (app_home / ".venv" / "bin" / "audiodoc").is_file()
    assert not (app_home / ".venv.new").exists()
    assert not (app_home / ".venv.prev").exists()
    assert "systemctl --user restart audiodoc.service" in result.stdout

    calls = [
        json.loads(line)
        for line in (app_home / "calls.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert calls[-1] == ["doctor", "--offline"]
    assert calls.count(["service", "install", "--user"]) == 1


def test_installer_upgrade_rolls_back_when_offline_doctor_fails(
    tmp_path: Path,
    local_release: tuple[str, Path],
) -> None:
    release_url, _release_dir = local_release
    user_home = tmp_path / "user"
    user_home.mkdir()
    app_home = user_home / "audiodoc"

    initial = run_installer(
        "--no-model",
        release_url=release_url,
        home=user_home,
    )
    assert initial.returncode == 0, initial.stdout + initial.stderr

    old_marker = app_home / ".venv" / "old-environment-marker"
    old_marker.write_text("old", encoding="utf-8")

    result = run_installer(
        "--upgrade",
        release_url=release_url,
        home=user_home,
        extra_env={"FAKE_DOCTOR_FAIL_OFFLINE": "1"},
    )

    assert result.returncode != 0
    assert "doctor --offline failed" in result.stderr
    assert old_marker.read_text(encoding="utf-8") == "old"
    assert not (app_home / ".venv.new").exists()
    assert not (app_home / ".venv.prev").exists()


def test_installer_upgrade_refuses_active_user_service(
    tmp_path: Path,
    local_release: tuple[str, Path],
) -> None:
    release_url, _release_dir = local_release
    user_home = tmp_path / "user"
    user_home.mkdir()
    app_home = user_home / "audiodoc"

    initial = run_installer(
        "--no-model",
        release_url=release_url,
        home=user_home,
    )
    assert initial.returncode == 0, initial.stdout + initial.stderr

    old_marker = app_home / ".venv" / "old-environment-marker"
    old_marker.write_text("old", encoding="utf-8")
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    systemctl = fake_bin / "systemctl"
    systemctl.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    systemctl.chmod(0o755)

    result = run_installer(
        "--upgrade",
        release_url=release_url,
        home=user_home,
        extra_env={"PATH": str(fake_bin) + os.pathsep + os.environ["PATH"]},
    )

    assert result.returncode != 0
    assert "user service is active" in result.stderr
    assert old_marker.read_text(encoding="utf-8") == "old"
    assert not (app_home / ".venv.new").exists()


def test_installer_upgrade_rejects_legacy_010_installation(
    tmp_path: Path,
    local_release: tuple[str, Path],
) -> None:
    release_url, _release_dir = local_release
    user_home = tmp_path / "user"
    user_home.mkdir()
    app_home = user_home / "audiodoc"

    initial = run_installer(
        "--no-model",
        release_url=release_url,
        home=user_home,
    )
    assert initial.returncode == 0, initial.stdout + initial.stderr

    legacy_entrypoint = app_home / "backend" / "main.py"
    legacy_entrypoint.parent.mkdir(parents=True)
    legacy_entrypoint.write_text("# Legacy audiodoc entry point\n", encoding="utf-8")

    package_path = next(
        (app_home / ".venv" / "lib").glob("python*/site-packages/audiodoc")
    )
    shutil.rmtree(package_path)

    result = run_installer(
        "--upgrade",
        release_url=release_url,
        home=user_home,
    )

    assert result.returncode != 0
    assert "Legacy audiodoc 0.1.0" in result.stderr
    assert (app_home / ".venv" / "bin" / "audiodoc").is_file()
