# Copyright (c) 2026 Nikolai Zelensky
from collections.abc import Iterator
from types import TracebackType
from typing import Self

class Rect:
    width: float
    height: float

class Pixmap:
    def tobytes(self, output: str = ...) -> bytes: ...

class Page:
    rect: Rect

    def get_text(self, option: str = ...) -> str: ...
    def get_pixmap(self, *, dpi: int = ..., alpha: bool = ...) -> Pixmap: ...

class Document:
    page_count: int

    def __enter__(self) -> Self: ...
    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...
    def __iter__(self) -> Iterator[Page]: ...

def open(*, stream: bytes, filetype: str) -> Document: ...
