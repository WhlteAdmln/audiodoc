# Copyright (c) 2026 Nikolai Zelensky
import io
import zipfile

import pytest

from audiodoc.document_engine.detection import detect_format


def test_mimetype_member_is_read_with_a_fixed_200_byte_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("mimetype", b"0" * (4 * 1024 * 1024))

    original_read = zipfile.ZipExtFile.read
    requested_sizes = []

    def tracked_read(self: object, n: int = -1) -> object:
        requested_sizes.append(n)
        return original_read(self, n)

    monkeypatch.setattr(zipfile.ZipExtFile, "read", tracked_read)
    assert detect_format(output.getvalue(), "unknown.zip") is None
    assert requested_sizes == [200]
