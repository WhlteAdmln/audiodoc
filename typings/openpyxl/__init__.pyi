# Copyright (c) 2026 Nikolai Zelensky

from collections.abc import Iterator
from os import PathLike
from typing import BinaryIO

class Worksheet:
    title: str

    def iter_rows(
        self,
        *,
        max_row: int | None = ...,
        max_col: int | None = ...,
        values_only: bool = ...,
    ) -> Iterator[tuple[object, ...]]: ...

class Workbook:
    worksheets: list[Worksheet]

    def close(self) -> None: ...

def load_workbook(
    filename: str | PathLike[str] | BinaryIO,
    *,
    read_only: bool = ...,
    data_only: bool = ...,
) -> Workbook: ...
