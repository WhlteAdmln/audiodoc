"""Проверки направлений импортов и финальной структуры проекта."""

import ast
from pathlib import Path


PROJECT_ROOT = Path(__file__).parents[2]
BACKEND_ROOT = PROJECT_ROOT / "backend"


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def _backend_packages(path: Path) -> set[str]:
    return {
        name.split(".")[1]
        for name in _imports(path)
        if name.startswith("backend.") and len(name.split(".")) > 1
    }


def test_document_engine_does_not_depend_on_api_transcription_or_config():
    forbidden = {"api", "transcription", "config"}
    for path in (BACKEND_ROOT / "document_engine").rglob("*.py"):
        assert not (_backend_packages(path) & forbidden), str(path)


def test_api_handlers_depend_on_the_application_services():
    document_api = _backend_packages(BACKEND_ROOT / "api" / "documents.py")
    transcription_api = _backend_packages(BACKEND_ROOT / "api" / "transcribe.py")

    assert "document_engine" in document_api
    assert "transcription" in transcription_api


def test_api_does_not_become_a_dependency_of_document_engine_or_transcription():
    for package in ("document_engine", "transcription"):
        for path in (BACKEND_ROOT / package).rglob("*.py"):
            assert "api" not in _backend_packages(path), str(path)


def test_errors_common_and_config_only_import_their_own_package():
    for package in ("errors", "common", "config"):
        for path in (BACKEND_ROOT / package).rglob("*.py"):
            foreign = _backend_packages(path) - {package}
            assert not foreign, (
                f"{path} imports other backend packages: {sorted(foreign)}"
            )


def test_document_engine_processor_shim_is_removed():
    assert not (BACKEND_ROOT / "document_engine" / "processor.py").exists()


def test_project_root_has_no_legacy_test_scripts_or_working_folders():
    assert not list(PROJECT_ROOT.glob("test_*.py"))
    assert not (PROJECT_ROOT / "test_documents").exists()
    assert not (PROJECT_ROOT / "uploads").exists()
