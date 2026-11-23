# Copyright (c) 2026 Nikolai Zelensky
"""Extract Excel cell text with row, column, time, and character limits."""

from io import BytesIO

from openpyxl import Workbook, load_workbook

from audiodoc.document_engine.extractors.base import (
    ExtractContext,
    add_chunk,
    add_rows,
    finish_extraction,
    make_context,
)
from audiodoc.document_engine.limits import MAX_SHEET_COLUMNS, MAX_SHEET_ROWS
from audiodoc.errors.messages import EXTRACTION_MESSAGES


def _row_text(row: tuple[object, ...]) -> str:
    """Join the cell values of a row, treating empty cells as blank."""
    return " | ".join("" if value is None else str(value) for value in row).strip()


def _extract_sheets(workbook: Workbook, ctx: ExtractContext, result: list[str]) -> None:
    """Append the text of every sheet until the budget or deadline ends."""
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
        add_rows(result, ctx, rows, _row_text, max_rows=MAX_SHEET_ROWS)
        if ctx.budget.is_truncated():
            break


def extract_xlsx(data: bytes, *, context: ExtractContext | None = None) -> str:
    """Extract XLSX cells, bounding even empty or maliciously inflated sheet ranges."""
    ctx = make_context(context)
    workbook = load_workbook(BytesIO(data), read_only=True, data_only=True)
    result: list[str] = []

    try:
        _extract_sheets(workbook, ctx, result)
    finally:
        workbook.close()

    return finish_extraction(result, ctx)
