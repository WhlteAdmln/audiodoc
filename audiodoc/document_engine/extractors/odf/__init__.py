# Copyright (c) 2026 Nikolai Zelensky
"""Load OpenDocument packages and dispatch to bounded ODT/ODS/ODP extractors."""

import io

from odf.opendocument import load as load_odf

from audiodoc.common.deadline import Deadline
from audiodoc.document_engine.extractors.base import ExtractContext, make_context
from audiodoc.document_engine.extractors.odf.odp import extract_odp
from audiodoc.document_engine.extractors.odf.ods import extract_ods
from audiodoc.document_engine.extractors.odf.odt import extract_odt

_EXTRACTORS = {"odt": extract_odt, "ods": extract_ods, "odp": extract_odp}


def extract_odf(
    data: bytes,
    filetype: str,
    *,
    context: ExtractContext | None = None,
    deadline: Deadline | None = None,
) -> str:
    """Load an ODF package and dispatch extraction with its shared context."""
    ctx = make_context(context, deadline=deadline)
    ctx.check()
    document = load_odf(io.BytesIO(data))
    extractor = _EXTRACTORS.get(filetype)
    if extractor is None:
        return ""
    return extractor(document, context=ctx)


__all__ = ["extract_odf", "extract_odp", "extract_ods", "extract_odt"]
