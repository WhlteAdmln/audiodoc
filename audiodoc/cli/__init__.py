# Copyright (c) 2026 Nikolai Zelensky
"""Command-line interface for the audiodoc server."""

from audiodoc.cli.main import main
from audiodoc.cli.parser import build_parser

__all__ = ["build_parser", "main"]
