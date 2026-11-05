"""Поиск внешних инструментов DjVuLibre."""

from dataclasses import dataclass
import shutil

from backend.errors.documents import DependencyMissingError


@dataclass(frozen=True)
class DjvuTools:
    """Пути к исполняемым файлам DjVuLibre."""

    djvutxt: str | None
    djvused: str | None
    ddjvu: str | None


def find_djvu_tools() -> DjvuTools:
    """Находит djvutxt, djvused и ddjvu в PATH."""
    return DjvuTools(
        djvutxt=shutil.which("djvutxt"),
        djvused=shutil.which("djvused"),
        ddjvu=shutil.which("ddjvu"),
    )


def require_djvutxt(tools: DjvuTools) -> str:
    """Проверяет наличие инструмента чтения текстового слоя."""
    if tools.djvutxt is None:
        raise DependencyMissingError()
    return tools.djvutxt
