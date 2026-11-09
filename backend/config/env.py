# Copyright (c) 2026 Nikolai Zelensky
"""Small, strict environment-variable readers shared by backend settings."""

import math
import os
from collections.abc import Mapping

from dotenv import load_dotenv

from backend.config.paths import PROJECT_ROOT


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


def get_float(
    name: str,
    default: str,
    minimum: float | None = None,
    maximum: float | None = None,
) -> float:
    """Read a finite float setting and enforce optional bounds."""
    value = os.getenv(name, default)

    try:
        result = float(value)
    except (TypeError, ValueError) as error:
        message = f"Настройка {name} должна быть числом. Получено: {value!r}"
        raise ValueError(message) from error

    if not math.isfinite(result):
        message = f"Настройка {name} должна быть конечным числом. Получено: {value!r}"
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
