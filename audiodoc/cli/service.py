# Copyright (c) 2026 Nikolai Zelensky
"""The service command: manage the systemd service."""

import argparse
import sys
from pathlib import Path

from audiodoc.env_readers import get_home_dir
from audiodoc.service import USER_MODE, install_service_unit, render_service_unit


def _print_or_install_unit(args: argparse.Namespace, home: Path) -> Path | None:
    """Print the unit and return None, or install it and return its path."""
    if args.print_unit:
        sys.stdout.write(render_service_unit(home, mode=args.service_mode))
        return None
    return install_service_unit(
        home,
        mode=args.service_mode,
        force=args.force,
    )


def handle_service_command(
    args: argparse.Namespace, parser: argparse.ArgumentParser
) -> int:
    """Handle systemd service installation."""
    home = get_home_dir()
    try:
        unit_path = _print_or_install_unit(args, home)
    except (OSError, ValueError) as error:
        parser.error(str(error))

    if unit_path is None:
        return 0

    sys.stdout.write(f"Installed {args.service_mode} systemd unit: {unit_path}\n")
    sys.stdout.write("The service was not enabled or started. When ready, run:\n")
    prefix = "systemctl --user" if args.service_mode == USER_MODE else "sudo systemctl"
    commands = (
        f"{prefix} daemon-reload",
        f"{prefix} enable --now audiodoc.service",
        f"{prefix} status audiodoc.service",
    )
    for command in commands:
        sys.stdout.write(f"  {command}\n")
    return 0
