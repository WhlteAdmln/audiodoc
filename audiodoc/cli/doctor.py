# Copyright (c) 2026 Nikolai Zelensky
"""The doctor command: check the audiodoc installation."""

import argparse
import os
import sys
from collections.abc import Sequence

from audiodoc.config import load_env_file
from audiodoc.doctor import (
    DJVULIBRE_CHECK_NAME,
    TESSERACT_CHECK_NAME,
    collect_doctor_checks,
)
from audiodoc.system_diagnostics import FAIL_STATUS, DiagnosticCheck


def handle_doctor_command(
    _args: argparse.Namespace, _parser: argparse.ArgumentParser
) -> int:
    """Handle installation diagnostics."""
    load_env_file()
    checks = (
        collect_doctor_checks(os.environ, offline=True)
        if _args.offline
        else collect_doctor_checks(os.environ)
    )
    for check in checks:
        sys.stdout.write(f"{check.status:4} {check.name}: {check.message}\n")

    install_commands = _native_install_commands(checks)
    if install_commands:
        sys.stdout.write("Install missing native tools with one of:\n")
        for distribution, command in install_commands:
            sys.stdout.write(f"  {distribution}: {command}\n")

    return 1 if any(check.status == FAIL_STATUS for check in checks) else 0


def _native_install_commands(
    checks: Sequence[DiagnosticCheck],
) -> tuple[tuple[str, str], ...]:
    """Return OS-specific installation commands for missing native tools."""
    failed_names = {check.name for check in checks if check.status == FAIL_STATUS}
    packages: dict[str, list[str]] = {
        "apt": [],
        "dnf": [],
        "pacman": [],
    }

    if TESSERACT_CHECK_NAME in failed_names:
        packages["apt"].extend(
            ("tesseract-ocr", "tesseract-ocr-rus", "tesseract-ocr-eng")
        )
        packages["dnf"].extend(
            ("tesseract", "tesseract-langpack-rus", "tesseract-langpack-eng")
        )
        packages["pacman"].extend(
            ("tesseract", "tesseract-data-rus", "tesseract-data-eng")
        )

    if DJVULIBRE_CHECK_NAME in failed_names:
        packages["apt"].append("djvulibre-bin")
        packages["dnf"].append("djvulibre")
        packages["pacman"].append("djvulibre")

    if not any(packages.values()):
        return ()

    return (
        ("Debian/Ubuntu", f"sudo apt install {' '.join(packages['apt'])}"),
        ("Fedora/RHEL", f"sudo dnf install {' '.join(packages['dnf'])}"),
        ("Arch Linux", f"sudo pacman -S {' '.join(packages['pacman'])}"),
    )
