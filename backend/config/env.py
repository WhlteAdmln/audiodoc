"""Small, strict environment-variable readers shared by backend settings."""

import math
import os


def get_bool(name: str, default: bool = False) -> bool:
    """Read a boolean environment variable using common spellings."""
    value = os.getenv(name)

    if value is None or not value.strip():
        return default

    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False

    raise ValueError(
        f"Настройка {name} должна быть true или false. Получено: {value!r}"
    )


def get_int(name: str, default: str, minimum: int = 1) -> int:
    """Read an integer setting and enforce its lower bound."""
    value = os.getenv(name, default)

    try:
        result = int(value)
    except (TypeError, ValueError) as error:
        raise ValueError(
            f"Настройка {name} должна быть целым числом. Получено: {value!r}"
        ) from error

    if result < minimum:
        raise ValueError(
            f"Настройка {name} должна быть не меньше {minimum}. Получено: {result}"
        )

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
        raise ValueError(
            f"Настройка {name} должна быть числом. Получено: {value!r}"
        ) from error

    if not math.isfinite(result):
        raise ValueError(
            f"Настройка {name} должна быть конечным числом. Получено: {value!r}"
        )

    if minimum is not None and result < minimum:
        raise ValueError(
            f"Настройка {name} должна быть не меньше {minimum}. Получено: {result}"
        )

    if maximum is not None and result > maximum:
        raise ValueError(
            f"Настройка {name} должна быть не больше {maximum}. Получено: {result}"
        )

    return result
