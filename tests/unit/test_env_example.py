"""Keep the documented environment template in sync with Settings."""

import ast
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SETTINGS_PATH = PROJECT_ROOT / "backend" / "config" / "settings.py"
ENV_EXAMPLE_PATH = PROJECT_ROOT / ".env.example"
_ENV_KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_SETTING_READERS = {"get_bool", "get_int", "get_float"}


def _read_settings_environment_names() -> set[str]:
    tree = ast.parse(SETTINGS_PATH.read_text(encoding="utf-8"))
    settings_class = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "Settings"
    )
    names: set[str] = set()

    for node in ast.walk(settings_class):
        if not isinstance(node, ast.Call) or not node.args:
            continue

        function = node.func
        reads_environment = (
            isinstance(function, ast.Attribute)
            and isinstance(function.value, ast.Name)
            and function.value.id == "os"
            and function.attr == "getenv"
        ) or (isinstance(function, ast.Name) and function.id in _SETTING_READERS)

        first_argument = node.args[0]
        if (
            reads_environment
            and isinstance(first_argument, ast.Constant)
            and isinstance(first_argument.value, str)
        ):
            names.add(first_argument.value)

    return names


def _read_env_example_names() -> set[str]:
    names: set[str] = set()
    for line_number, raw_line in enumerate(
        ENV_EXAMPLE_PATH.read_text(encoding="utf-8").splitlines(), start=1
    ):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        key, separator, _value = line.partition("=")
        assert separator, f"Invalid .env.example line {line_number}: {raw_line!r}"
        assert _ENV_KEY_RE.fullmatch(key), (
            f"Invalid environment variable on .env.example line {line_number}: {key!r}"
        )
        assert key not in names, f"Duplicate variable in .env.example: {key}"
        names.add(key)

    return names


def test_env_example_matches_settings_environment_variables():
    settings_names = _read_settings_environment_names()
    example_names = _read_env_example_names()

    missing = sorted(settings_names - example_names)
    extra = sorted(example_names - settings_names)

    assert not missing, (
        ".env.example and backend/config/settings.py are out of sync. "
        f"Missing from .env.example: {missing}"
    )
    assert not extra, (
        ".env.example and backend/config/settings.py are out of sync. "
        f"not read by Settings: {extra}"
    )
