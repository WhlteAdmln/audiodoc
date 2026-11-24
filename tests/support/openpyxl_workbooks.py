# Copyright (c) 2026 Nikolai Zelensky
"""Fake openpyxl workbooks that record how the extractor reads them."""

from collections.abc import Iterator, Sequence


class FakeSheet:
    """Yield fixed rows and remember the arguments of the last read."""

    def __init__(self, title: str, rows: Sequence[tuple[object, ...]]) -> None:
        """Store the sheet title and its rows."""
        self.title = title
        self.rows = rows
        self.read_arguments: dict[str, object] = {}

    def iter_rows(
        self, *, max_row: object, max_col: object, values_only: object
    ) -> Iterator[tuple[object, ...]]:
        """Record the read arguments and yield every stored row."""
        self.read_arguments = {
            "max_row": max_row,
            "max_col": max_col,
            "values_only": values_only,
        }
        yield from self.rows


class FakeWorkbook:
    """Hold fake sheets and remember whether it was closed."""

    def __init__(self, worksheets: Sequence[FakeSheet]) -> None:
        """Store the sheets."""
        self.worksheets = list(worksheets)
        self.closed = False

    def close(self) -> None:
        """Mark the workbook as closed."""
        self.closed = True
