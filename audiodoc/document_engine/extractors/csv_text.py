# Copyright (c) 2026 Nikolai Zelensky
"""Stream CSV rows into the result without repeated full-list length sums."""

import csv
import io
from collections.abc import Iterator

from audiodoc.document_engine.extractors.base import (
    ExtractContext,
    add_chunk,
    make_context,
)
from audiodoc.errors.documents import CsvFieldTooLargeError

_FIELD_LIMIT_ERROR_PREFIX = "field larger than field limit"


def extract_csv(data: bytes, *, context: ExtractContext | None = None) -> str:
    """Extract CSV rows until additional non-empty text exceeds the shared budget."""
    ctx = make_context(context)
    text = data.decode("utf-8-sig", errors="replace")
    try:
        dialect = csv.Sniffer().sniff(text[:8192], delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel

    result: list[str] = []
    for row in _read_rows(text, dialect):
        ctx.check()
        line = " | ".join(row).strip()
        if line:
            add_chunk(result, ctx, line)
        if ctx.budget.truncated:
            break
    return "\n".join(result)


def _read_rows(
    text: str, dialect: type[csv.Dialect] | csv.Dialect
) -> Iterator[list[str]]:
    try:
        yield from csv.reader(io.StringIO(text), dialect)
    except csv.Error as error:
        if str(error).startswith(_FIELD_LIMIT_ERROR_PREFIX):
            raise CsvFieldTooLargeError from error
        raise
