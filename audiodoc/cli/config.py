# Copyright (c) 2026 Nikolai Zelensky
"""The config command: inspect application configuration."""

import argparse
import os
import sys
import warnings
from collections.abc import Mapping

from audiodoc.api.auth import check_security_settings
from audiodoc.config import ConfigError, Settings, load_env_file, load_settings
from audiodoc.env_readers import get_bool, get_log_level

CONFIG_CHECK_COMMAND = "check"


def handle_config_command(
    args: argparse.Namespace, _parser: argparse.ArgumentParser
) -> int:
    """Handle configuration inspection commands."""
    if args.config_command == CONFIG_CHECK_COMMAND:
        load_env_file()
        problems = _configuration_problems(os.environ)
        if problems:
            sys.stdout.write("Configuration has problems:\n")
            for problem in problems:
                sys.stdout.write(f"- {problem}\n")
            return 1
        sys.stdout.write("Configuration is valid.\n")
        return 0
    return 2


def _configuration_problems(environ: Mapping[str, str]) -> list[str]:
    """Collect configuration and security problems without exposing secrets."""
    problems: list[str] = []
    try:
        configured_settings = load_settings(environ)
    except ConfigError as error:
        problems.extend(message.partition(" Got:")[0] for message in error.errors)
        configured_settings = _settings_for_security_check(environ)

    try:
        check_security_settings(configured_settings)
    except RuntimeError as error:
        problems.append(str(error))

    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always", RuntimeWarning)
        get_log_level(environ=environ)

    if captured:
        problems.append("Invalid LOG_LEVEL; falling back to INFO.")

    return problems


def _settings_for_security_check(environ: Mapping[str, str]) -> Settings:
    """Build the authentication settings even when other settings are invalid."""
    audio_key = environ.get("AUDIODOC_AUDIO_KEY", "").strip()
    document_key = environ.get("AUDIODOC_DOCUMENT_KEY", "").strip()

    try:
        allow_unauthenticated = get_bool("ALLOW_UNAUTHENTICATED", environ=environ)
    except ValueError:
        allow_unauthenticated = False

    return Settings(
        AUDIODOC_AUDIO_KEY=audio_key,
        AUDIODOC_DOCUMENT_KEY=document_key,
        ALLOW_UNAUTHENTICATED=allow_unauthenticated,
    )
