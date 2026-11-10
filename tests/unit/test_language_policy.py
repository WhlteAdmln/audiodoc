# Copyright (c) 2026 Nikolai Zelensky
import ast
import io
import tokenize
import unicodedata
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = PROJECT_ROOT / "backend"
TESTS_ROOT = PROJECT_ROOT / "tests"
ALLOWLIST_PATH = TESTS_ROOT / "language_allowlist.txt"
RUSSIAN_MESSAGES_PATH = Path("backend/errors/messages.py")


def _contains_cyrillic(value: str) -> bool:
    return any(
        unicodedata.name(character, "").startswith("CYRILLIC") for character in value
    )


def _find_violations(path: Path) -> set[str]:
    source = path.read_text(encoding="utf-8")
    relative_path = path.relative_to(PROJECT_ROOT)
    violations: set[str] = set()

    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type == tokenize.COMMENT and _contains_cyrillic(token.string):
            violations.add("comment")

    syntax_tree = ast.parse(source, filename=str(relative_path))

    for node in ast.walk(syntax_tree):
        if isinstance(
            node,
            (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef),
        ):
            docstring = ast.get_docstring(node, clean=False)
            if docstring is not None and _contains_cyrillic(docstring):
                violations.add("docstring")

        if (
            relative_path.parts[0] == "backend"
            and relative_path != RUSSIAN_MESSAGES_PATH
            and isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and _contains_cyrillic(node.value)
        ):
            violations.add("string literal")

    return violations


def _collect_violations() -> dict[str, set[str]]:
    violations_by_path: dict[str, set[str]] = {}

    for root in (BACKEND_ROOT, TESTS_ROOT):
        for path in sorted(root.rglob("*.py")):
            violations = _find_violations(path)
            if violations:
                relative_path = path.relative_to(PROJECT_ROOT).as_posix()
                violations_by_path[relative_path] = violations

    return violations_by_path


def test_python_language_policy_allowlist_is_current() -> None:
    allowlist = {
        line.strip()
        for line in ALLOWLIST_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    }
    violations = _collect_violations()
    violating_paths = set(violations)

    missing_paths = sorted(violating_paths - allowlist)
    stale_paths = sorted(allowlist - violating_paths)
    missing_details = ", ".join(
        f"{path} ({', '.join(sorted(violations[path]))})" for path in missing_paths
    )

    assert not missing_paths, (
        "Python files violate the language policy but are not allowlisted: "
        f"{missing_details}"
    )
    assert not stale_paths, (
        "Allowlisted files no longer violate the language policy: "
        + ", ".join(stale_paths)
    )
