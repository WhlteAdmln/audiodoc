# Copyright (c) 2026 Nikolai Zelensky
"""Property-based tests for document detection and bounded text processing."""

import asyncio
import io
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from starlette.datastructures import UploadFile
from starlette.exceptions import HTTPException

import backend.common.limited_upload as upload_limits
from backend.common.limited_upload import save_upload_limited
from backend.common.text_budget import TextBudget
from backend.document_engine.detection import detect_format
from backend.document_engine.result import build_result


@given(
    data=st.one_of(
        st.binary(max_size=4096),
        st.binary(max_size=4094).map(lambda payload: b"PK" + payload),
    ),
    filename=st.one_of(st.none(), st.text(max_size=255)),
)
@settings(max_examples=200)
def test_detect_format_never_raises_for_random_bytes_and_names(
    data: bytes,
    filename: str | None,
) -> None:
    detected = detect_format(data, filename)

    assert detected is None or isinstance(detected, str)


@given(
    limit=st.integers(min_value=1, max_value=1024),
    chunks=st.lists(st.text(max_size=256), max_size=16),
    separator_length=st.integers(min_value=0, max_value=8),
)
@settings(max_examples=200)
def test_text_budget_never_exceeds_limit_and_reports_exact_truncation(
    limit: int,
    chunks: list[str],
    separator_length: int,
) -> None:
    budget = TextBudget(limit)
    expected_truncated = False

    for chunk in chunks:
        piece = budget.add(chunk, separator_length=separator_length)
        if len(piece) < len(chunk):
            expected_truncated = True

        assert budget.truncated is expected_truncated
        assert budget.used <= limit


@given(
    data=st.binary(max_size=4096),
    limit=st.integers(min_value=1, max_value=1024),
)
@settings(max_examples=200)
def test_save_upload_limited_never_writes_more_than_limit(
    data: bytes,
    limit: int,
) -> None:
    with TemporaryDirectory() as temp_dir:
        destination = Path(temp_dir) / "upload.bin"
        upload = UploadFile(
            file=io.BytesIO(data),
            filename="upload.bin",
        )

        with patch.object(upload_limits, "CHUNK_SIZE", 32):
            if len(data) > limit:
                with pytest.raises(HTTPException) as error:
                    asyncio.run(save_upload_limited(upload, destination, limit))

                assert error.value.status_code == 413
            else:
                saved = asyncio.run(save_upload_limited(upload, destination, limit))
                assert saved == len(data)

        assert destination.stat().st_size <= limit


@given(
    text=st.text(max_size=8192),
    truncated=st.booleans(),
)
@settings(max_examples=200)
def test_document_text_normalization_is_idempotent(
    text: str,
    truncated: bool,
) -> None:
    first = build_result("txt", text, truncated=truncated)
    second = build_result(
        first["format"],
        first["text"],
        truncated=first["truncated"],
    )

    assert second == first
