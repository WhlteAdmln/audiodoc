"""Stream CSV rows into the result without repeated full-list length sums."""

import csv
import io

from backend.document_engine.extractors.base import (
    ExtractContext,
    add_chunk,
    make_context,
)


def extract_csv(data: bytes, *, context: ExtractContext | None = None) -> str:
    """Extract CSV rows until additional non-empty text exceeds the shared budget."""
    ctx = make_context(context)
    text = data.decode("utf-8-sig", errors="replace")
    try:
        dialect = csv.Sniffer().sniff(text[:8192])
    except csv.Error:
        dialect = csv.excel

    result: list[str] = []
    for row in csv.reader(io.StringIO(text), dialect):
        ctx.check()
        line = " | ".join(row).strip()
        if line:
            add_chunk(result, ctx, line)
        if ctx.budget.truncated:
            break
    return "\n".join(result)
