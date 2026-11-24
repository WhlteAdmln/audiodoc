# Copyright (c) 2026 Nikolai Zelensky
"""Publish a fake audiodoc release and serve it over local HTTP."""

from __future__ import annotations

import base64
import csv
import functools
import hashlib
import http.server
import io
import threading
import zipfile
from contextlib import contextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

_FAKE_CLI_SOURCE = """
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
        if os.environ.get("FAKE_DOCTOR_FAIL") == "1":
            print("FAIL forced doctor failure.")
            return 1
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
        if "--print" in args:
            unit = (
                "[Unit]\\n"
                "Description=audiodoc API service\\n"
                "After=network-online.target\\n"
                "Wants=network-online.target\\n\\n"
                "[Service]\\n"
                "Type=simple\\n"
                f"WorkingDirectory={home}\\n"
                f"EnvironmentFile={home}/.env\\n"
                f'Environment="AUDIODOC_HOME={home}"\\n'
                "Environment=PYTHONUNBUFFERED=1\\n"
                f'ExecStart="{home}/.venv/bin/audiodoc" run\\n'
                "Restart=on-failure\\n"
                "RestartSec=5\\n"
                "UMask=0077\\n\\n"
                "[Install]\\n"
                "WantedBy=default.target\\n"
            )
            sys.stdout.write(unit)
            return 0
        (home / "service-installed").write_text("ok", encoding="utf-8")
        return 0

    return 2
"""


@dataclass(frozen=True, slots=True)
class LocalRelease:
    """A release directory and the URL that serves it."""

    url: str
    directory: Path


def _record_digest(content: bytes) -> str:
    digest = base64.urlsafe_b64encode(hashlib.sha256(content).digest())
    return "sha256=" + digest.rstrip(b"=").decode("ascii")


def build_wheel(directory: Path, *, version: str = "1.2.3") -> Path:
    """Write a minimal wheel whose ``audiodoc`` CLI records every call.

    Args:
        directory: The release directory that receives the wheel.
        version: The distribution version written into the metadata.

    Returns:
        The path of the new wheel.
    """
    distribution = f"audiodoc-{version}.dist-info"
    files = {
        "audiodoc/__init__.py": b"",
        "audiodoc/__main__.py": (
            b"from audiodoc.cli import main\nraise SystemExit(main())\n"
        ),
        "audiodoc/cli.py": _FAKE_CLI_SOURCE.encode("utf-8"),
        f"{distribution}/METADATA": (
            "Metadata-Version: 2.1\n"
            "Name: audiodoc\n"
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
    record_name = f"{distribution}/RECORD"
    rows = [
        (name, _record_digest(content), str(len(content)))
        for name, content in files.items()
    ]
    record_stream = io.StringIO()
    csv.writer(record_stream, lineterminator="\n").writerows(
        [*rows, (record_name, "", "")]
    )
    files[record_name] = record_stream.getvalue().encode("utf-8")

    wheel_path = directory / f"audiodoc-{version}-py3-none-any.whl"
    with zipfile.ZipFile(wheel_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return wheel_path


def checksum_line(path: Path) -> str:
    """Return the ``SHA256SUMS`` line of one release asset."""
    return f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}"


def write_manifest(directory: Path, lines: list[str]) -> None:
    """Replace the ``SHA256SUMS`` manifest of a release directory."""
    text = "".join(f"{line}\n" for line in lines)
    (directory / "SHA256SUMS").write_text(text, encoding="utf-8")


def publish(directory: Path, *, version: str = "1.2.3") -> Path:
    """Write a wheel, empty constraints and a matching manifest.

    Args:
        directory: The release directory.
        version: The version of the new wheel.

    Returns:
        The path of the new wheel.
    """
    wheel_path = build_wheel(directory, version=version)
    constraints = directory / "constraints.txt"
    constraints.write_text("", encoding="utf-8")
    archive_line = hashlib.sha256(b"release-archive").hexdigest()
    write_manifest(
        directory,
        [
            f"{archive_line}  audiodoc-{version}.zip",
            checksum_line(wheel_path),
            checksum_line(constraints),
        ],
    )
    return wheel_path


@contextmanager
def serve_release(directory: Path) -> Iterator[LocalRelease]:
    """Serve a release directory on a free localhost port until the block ends."""
    server = http.server.ThreadingHTTPServer(
        ("127.0.0.1", 0),
        functools.partial(
            http.server.SimpleHTTPRequestHandler, directory=str(directory)
        ),
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield LocalRelease(f"http://127.0.0.1:{server.server_address[1]}", directory)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
