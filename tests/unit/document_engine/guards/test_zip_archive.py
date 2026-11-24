# Copyright (c) 2026 Nikolai Zelensky

"""Tests for guards zip archive."""

from __future__ import annotations

import io
import stat
import zipfile

import pytest

from audiodoc.document_engine.guards import zip_archive as zip_guard
from audiodoc.document_engine.guards.zip_archive import validate_zip_archive
from tests.support.zip_archives import ZipMember, lying_zip


def _archive(members: dict[str, bytes], *, external_attr: int = 0) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as archive:
        for name, data in members.items():
            info = zipfile.ZipInfo(name)
            info.external_attr = external_attr
            archive.writestr(info, data)
    return output.getvalue()


def _rejection(data: bytes) -> str:
    with pytest.raises(ValueError, match=r".") as caught:
        validate_zip_archive(data)
    return str(caught.value)


@pytest.mark.parametrize(
    "name",
    [
        "../evil.txt",
        "/etc/passwd",
        "C:/Windows/win.ini",
        "D:relative.xml",
        "..\\secret.txt",
        "word/../../etc/hosts",
        "media\\..\\..\\boot.ini",
    ],
)
def test_rejects_member_paths_that_escape_the_archive(name: str) -> None:
    data = _archive({name: b"payload"})

    message = _rejection(data)

    expected = f"Unsafe ZIP member path: {name}"
    assert message == expected, "an escaping member path was accepted"


def test_rejects_member_name_with_a_null_character() -> None:
    data = _archive({"reportX.txt": b"%"}).replace(b"reportX", b"report\x00")

    message = _rejection(data)

    expected = "Unsafe ZIP member path: report"
    assert message == expected, "a member name with NUL was accepted"


def test_rejects_symbolic_link_member() -> None:
    link_mode = (stat.S_IFLNK | 0o777) << 16
    data = _archive({"styles.xml": b"/etc/shadow"}, external_attr=link_mode)

    message = _rejection(data)

    expected = "ZIP symbolic links are not allowed: styles.xml"
    assert message == expected, "a symbolic link member was accepted"


@pytest.mark.parametrize("name", ["inner.zip", "Вложение.ZIP", "a/b/c.Zip"])
def test_rejects_member_named_as_nested_archive(name: str) -> None:
    data = _archive({name: b"\x00\x01"})

    message = _rejection(data)

    expected = f"Nested ZIP archives are not allowed: {name}"
    assert message == expected, "a nested archive name was accepted"


@pytest.mark.parametrize(
    "signature", [b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08"], ids=repr
)
def test_rejects_member_whose_content_is_a_nested_archive(signature: bytes) -> None:
    data = _archive({"media/image1.bin": signature + b"\x14\x00rest"})

    message = _rejection(data)

    expected = "Nested ZIP archive detected: media/image1.bin"
    assert message == expected, "nested archive content was accepted"


def test_rejects_archive_with_one_file_over_the_count_limit() -> None:
    members = {f"part{index:03}.xml": b"<p/>" for index in range(101)}

    message = _rejection(_archive(members))

    expected = "Too many files in archive: 101"
    assert message == expected, "the file count limit was not applied"


def test_checks_members_of_an_archive_at_the_count_limit() -> None:
    members = {f"part{index:03}.xml": b"<p/>" for index in range(99)}
    members["../last.xml"] = b"<p/>"

    message = _rejection(_archive(members))

    expected = "Unsafe ZIP member path: ../last.xml"
    assert message == expected, "an archive at the count limit was not checked"


def test_rejects_member_whose_declared_size_exceeds_the_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(zip_guard, "MAX_ARCHIVE_FILE_SIZE", 2)

    message = _rejection(_archive({"big.bin": b"\x7f\x7f\x7f"}))

    expected = "File inside archive is too large: big.bin"
    assert message == expected, "the declared member size limit was not applied"


def test_rejects_members_whose_declared_total_exceeds_the_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(zip_guard, "MAX_ARCHIVE_UNPACKED_SIZE", 5)
    data = _archive({"one.xml": b"<a/>", "two.xml": b"<b/>"})

    message = _rejection(data)

    expected = "Total unpacked archive size exceeds the limit"
    assert message == expected, "the declared total size limit was not applied"


def test_rejects_nonempty_member_with_zero_compressed_size() -> None:
    archive = lying_zip([ZipMember("Отчёт.txt", b"z", declared_compress_size=0)])

    message = _rejection(archive)

    expected = "Suspicious compressed file size: Отчёт.txt"
    assert message == expected, "a zero compressed size was accepted"


def test_rejects_member_with_declared_compression_ratio_over_the_limit() -> None:
    archive = lying_zip(
        [ZipMember("bomb.txt", b"Q" * 65536, compression=zipfile.ZIP_DEFLATED)]
    )

    message = _rejection(archive)

    expected = "Suspicious compression ratio: bomb.txt"
    assert message == expected, "a highly compressed member was accepted"


def test_rejects_member_larger_than_its_declared_size_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(zip_guard, "MAX_ARCHIVE_FILE_SIZE", 2)
    archive = lying_zip([ZipMember("ä/b.bin", b"\x00\xff\x10", declared_file_size=2)])

    message = _rejection(archive)

    expected = "Actual ZIP member size exceeds the limit: ä/b.bin"
    assert message == expected, "a member that lies about its size was accepted"


def test_rejects_members_whose_actual_total_exceeds_the_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(zip_guard, "MAX_ARCHIVE_UNPACKED_SIZE", 4)
    archive = lying_zip(
        [
            ZipMember("first.xml", b"<a/"),
            ZipMember("second.xml", b"\t\n", declared_file_size=1),
        ],
    )

    message = _rejection(archive)

    expected = "Total unpacked archive size exceeds the limit"
    assert message == expected, "members that lie about the total were accepted"


def test_rejects_member_that_inflates_beyond_the_ratio(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(zip_guard, "MAX_ARCHIVE_COMPRESSION_RATIO", 1)
    archive = lying_zip(
        [
            ZipMember(
                "bomb.txt",
                b"Q" * 4096,
                compression=zipfile.ZIP_DEFLATED,
                declared_file_size=3,
            ),
        ],
    )

    message = _rejection(archive)

    expected = "Actual ZIP compression ratio is too high: bomb.txt"
    assert message == expected, "a member that inflates beyond the ratio passed"


def test_rejects_member_shorter_than_its_declared_size() -> None:
    archive = lying_zip([ZipMember("content.xml", b"<x/>", declared_file_size=6)])

    message = _rejection(archive)

    expected = "Declared file size does not match actual size: content.xml"
    assert message == expected, "a size mismatch was accepted"


def test_reports_member_with_a_wrong_checksum_as_corrupt() -> None:
    data = _archive({"note.txt": b"original text"}).replace(b"original", b"tampered")

    message = _rejection(data)

    expected = "Corrupt ZIP archive"
    assert message == expected, "a corrupted member was accepted"


@pytest.mark.parametrize(
    "data",
    [b"", b"not a zip archive", b"PK\x03\x04", b"%PDF-1.7\n%\xe2\xe3"],
    ids=repr,
)
def test_rejects_data_that_is_not_a_zip_container(data: bytes) -> None:
    message = _rejection(data)

    expected = "Invalid ZIP container"
    assert message == expected, "non-ZIP data was accepted"


def test_rejects_archive_cut_before_its_central_directory() -> None:
    data = _archive({"word/document.xml": b"<w:document/>"})

    message = _rejection(data[:-30])

    expected = "Invalid ZIP container"
    assert message == expected, "a truncated archive was accepted"
