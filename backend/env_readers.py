# VENDORED: keep identical in bot-obormot and audiodoc. Source of truth: audiodoc.
# Copyright (c) 2026 Nikolai Zelensky
"""Shared environment-variable readers."""

import math
import os
import warnings
from collections.abc import Mapping
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def load_env_file() -> None:
    """Load the project environment file without overriding exported variables."""
    load_dotenv(PROJECT_ROOT / ".env", override=False)


def get_bool(
    name: str, default: bool = False, *, environ: Mapping[str, str] | None = None
) -> bool:
    """Read a boolean environment variable using common spellings."""
    source = os.environ if environ is None else environ
    value = source.get(name)

    if value is None or not value.strip():
        return default

    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False

    message = f"Настройка {name} должна быть true или false. Получено: {value!r}"
    raise ValueError(message)


def get_int(
    name: str,
    default: str,
    minimum: int = 1,
    *,
    environ: Mapping[str, str] | None = None,
) -> int:
    """Read an integer setting and enforce its lower bound."""
    source = os.environ if environ is None else environ
    value = source.get(name, default)

    try:
        result = int(value)
    except (TypeError, ValueError) as error:
        message = f"Настройка {name} должна быть целым числом. Получено: {value!r}"
        raise ValueError(message) from error

    if result < minimum:
        message = f"Настройка {name} должна быть не меньше {minimum}."
        message += f" Получено: {result}"
        raise ValueError(message)

    return result


def get_optional_int(
    name: str,
    minimum: int = 1,
    *,
    environ: Mapping[str, str] | None = None,
) -> int | None:
    """Read an optional integer setting; an empty value means None."""
    source = os.environ if environ is None else environ
    value = source.get(name)

    if value is None or not value.strip():
        return None

    try:
        result = int(value)
    except (TypeError, ValueError) as error:
        message = f"Настройка {name} должна быть целым числом. Получено: {value!r}"
        raise ValueError(message) from error

    if result < minimum:
        message = f"Настройка {name} должна быть не меньше {minimum}."
        message += f" Получено: {result}"
        raise ValueError(message)

    return result


def get_float(
    name: str,
    default: str,
    minimum: float | None = None,
    maximum: float | None = None,
    *,
    environ: Mapping[str, str] | None = None,
) -> float:
    """Read a finite float setting and enforce optional bounds."""
    source = os.environ if environ is None else environ
    value = source.get(name, default)

    try:
        result = float(value)
    except (TypeError, ValueError) as error:
        message = f"Настройка {name} должна быть числом. Получено: {value!r}"
        raise ValueError(message) from error

    if not math.isfinite(result):
        message = f"Настройка {name} должна быть конечным числом."
        message += f" Получено: {value!r}"
        raise ValueError(message)

    if minimum is not None and result < minimum:
        message = f"Настройка {name} должна быть не меньше {minimum}."
        message += f" Получено: {result}"
        raise ValueError(message)

    if maximum is not None and result > maximum:
        message = f"Настройка {name} должна быть не больше {maximum}."
        message += f" Получено: {result}"
        raise ValueError(message)

    return result


def get_log_level(*, environ: Mapping[str, str] | None = None) -> str:
    """Return a valid logging level, defaulting to INFO for invalid values."""
    source = os.environ if environ is None else environ
    value = source.get("LOG_LEVEL", "INFO").strip().upper()

    allowed_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
    if value not in allowed_levels:
        warnings.warn(
            f"Некорректный LOG_LEVEL={value!r}. Используется уровень INFO.",
            RuntimeWarning,
            stacklevel=2,
        )
        return "INFO"

    return value


def parse_ids(name: str, *, environ: Mapping[str, str] | None = None) -> set[int]:
    """Read a comma-separated environment variable containing positive IDs."""
    source = os.environ if environ is None else environ
    value = source.get(name, "").strip()

    if not value:
        return set()

    result: set[int] = set()
    for raw_item in value.split(","):
        item = raw_item.strip()
        if not item:
            continue

        try:
            user_id = int(item)
        except ValueError as error:
            message = f"Настройка {name} содержит некорректный ID: {item!r}"
            raise ValueError(message) from error

        if user_id <= 0:
            message = f"ID в настройке {name} должен быть положительным: {user_id}"
            raise ValueError(message)

        result.add(user_id)

    return result
