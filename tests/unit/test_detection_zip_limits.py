import io
import zipfile

from backend.document_engine.detection import detect_format


def test_mimetype_member_is_read_with_a_fixed_200_byte_limit(monkeypatch):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("mimetype", b"0" * (4 * 1024 * 1024))

    original_read = zipfile.ZipExtFile.read
    requested_sizes = []

    def tracked_read(self, n=-1):
        requested_sizes.append(n)
        return original_read(self, n)

    monkeypatch.setattr(zipfile.ZipExtFile, "read", tracked_read)
    assert detect_format(output.getvalue(), "unknown.zip") is None
    assert requested_sizes == [200]
