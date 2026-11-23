# Copyright (c) 2026 Nikolai Zelensky
"""Entry point that dispatches audiodoc commands to their handlers."""

import argparse
import sys
from collections.abc import Callable, Sequence

from audiodoc.cli.config import handle_config_command
from audiodoc.cli.doctor import handle_doctor_command
from audiodoc.cli.init import handle_init_command
from audiodoc.cli.model import handle_model_command
from audiodoc.cli.pair import handle_pair_command
from audiodoc.cli.parser import build_parser
from audiodoc.cli.run import handle_run_command
from audiodoc.cli.service import handle_service_command
from audiodoc.cli.version import handle_version_command

CommandHandler = Callable[[argparse.Namespace, argparse.ArgumentParser], int]


def main(argv: Sequence[str] | None = None) -> int:
    """Run the audiodoc command-line interface."""
    parser = build_parser()
    args = parser.parse_args(argv)

    handlers: dict[str, CommandHandler] = {
        "run": handle_run_command,
        "version": handle_version_command,
        "doctor": handle_doctor_command,
        "init": handle_init_command,
        "pair": handle_pair_command,
        "model": handle_model_command,
        "config": handle_config_command,
        "service": handle_service_command,
    }
    handler = handlers.get(args.command)
    if handler is None:
        parser.print_usage(sys.stderr)
        sys.stderr.write(f"{parser.prog}: error: Unsupported command.\n")
        return 2
    return handler(args, parser)
