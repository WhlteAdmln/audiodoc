"""Extract ODS sheets with lazy row/cell traversal and fixed output limits."""

from collections.abc import Iterator

from odf import teletype
from odf.table import Table

from backend.document_engine.extractors.base import (
    ExtractContext,
    add_chunk,
    make_context,
    odf_attribute,
    odf_elements,
)
from backend.document_engine.limits import MAX_SHEET_COLUMNS, MAX_SHEET_ROWS

_TABLE_ROW_QNAME = ("urn:oasis:names:tc:opendocument:xmlns:table:1.0", "table-row")
_TABLE_CELL_QNAME = ("urn:oasis:names:tc:opendocument:xmlns:table:1.0", "table-cell")


def _iter_descendants(element: object, qname: tuple[str, str]) -> Iterator[object]:
    """Yield matching ODF descendants lazily with an iterator stack."""
    stack = [iter(getattr(element, "childNodes", ()))]
    while stack:
        try:
            node = next(stack[-1])
        except StopIteration:
            stack.pop()
            continue
        if getattr(node, "qname", None) == qname:
            yield node
        children = getattr(node, "childNodes", ())
        if children:
            stack.append(iter(children))


def extract_ods(document: object, *, context: ExtractContext | None = None) -> str:
    """Extract at most the configured number of rows and columns from each sheet."""
    ctx = make_context(context)
    result: list[str] = []

    for table in odf_elements(document, Table):
        ctx.check()
        add_chunk(result, ctx, f"--- Лист: {odf_attribute(table, 'name')} ---")
        if ctx.budget.is_truncated():
            break

        for row_number, row in enumerate(
            _iter_descendants(table, _TABLE_ROW_QNAME), start=1
        ):
            ctx.check()
            cells = _iter_descendants(row, _TABLE_CELL_QNAME)
            cell_text = []
            for index, cell in enumerate(cells):
                if index >= MAX_SHEET_COLUMNS:
                    break
                cell_text.append(teletype.extractText(cell).strip())
            line = " | ".join(cell_text)
            if line.strip():
                add_chunk(result, ctx, line)
            if row_number >= MAX_SHEET_ROWS or ctx.budget.is_truncated():
                break
        if ctx.budget.is_truncated():
            break

    ctx.check()
    return "\n".join(result)
