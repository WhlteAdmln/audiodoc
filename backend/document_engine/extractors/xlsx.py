# Copyright (c) 2026 Nikolai Zelensky
"""Extract Excel cell text with row, column, time, and character limits."""

from io import BytesIO

from openpyxl import load_workbook

from backend.document_engine.extractors.base import (
    ExtractContext,
    add_chunk,
    make_context,
)
from backend.document_engine.limits import MAX_SHEET_COLUMNS, MAX_SHEET_ROWS
from backend.errors.messages import EXTRACTION_MESSAGES


def extract_xlsx(data: bytes, *, context: ExtractContext | None = None) -> str:
    """Extract XLSX cells, bounding even empty or maliciously inflated sheet ranges."""
    ctx = make_context(context)
    workbook = load_workbook(BytesIO(data), read_only=True, data_only=True)
    result: list[str] = []

    try:
        for sheet in workbook.worksheets:
            ctx.check()
            add_chunk(
                result,
                ctx,
                EXTRACTION_MESSAGES["xlsx_sheet_label"].format(name=sheet.title),
            )
            if ctx.budget.is_truncated():
                break

            rows = sheet.iter_rows(
                max_row=MAX_SHEET_ROWS,
                max_col=MAX_SHEET_COLUMNS,
                values_only=True,
            )
            for row_number, row in enumerate(rows, start=1):
                ctx.check()
                line = " | ".join(
                    "" if value is None else str(value) for value in row
                ).strip()
                if line:
                    add_chunk(result, ctx, line)
                if row_number >= MAX_SHEET_ROWS or ctx.budget.is_truncated():
                    break
            if ctx.budget.is_truncated():
                break
    finally:
        workbook.close()

    ctx.check()
    return "\n".join(result)
