# Copyright (c) 2026 Nikolai Zelensky
"""Backward-compatible import for the logging setup."""

from backend.logging_setup import LOG_FORMAT, configure_logging

__all__ = ["LOG_FORMAT", "configure_logging"]
