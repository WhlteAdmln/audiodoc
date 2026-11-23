# Copyright (c) 2026 Nikolai Zelensky
"""The version command: show the installed version."""

import argparse
import sys
from importlib.metadata import version as package_version


def handle_version_command(
    _args: argparse.Namespace, _parser: argparse.ArgumentParser
) -> int:
    """Handle the version command."""
    sys.stdout.write(f"audiodoc {package_version('audiodoc')}\n")
    return 0
