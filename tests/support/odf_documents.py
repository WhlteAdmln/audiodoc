# Copyright (c) 2026 Nikolai Zelensky
"""ODF loading helper for extractor tests."""

import io

from odf.opendocument import load as load_odf


def load_document(data: bytes) -> object:
    """Load an ODF document from bytes."""
    return load_odf(io.BytesIO(data))
