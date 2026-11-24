# Copyright (c) 2026 Nikolai Zelensky
"""Hostile document payloads for the Document Engine pipeline tests."""

import io
import stat
import zipfile

ZipEntry = tuple[str | zipfile.ZipInfo, bytes]


def make_nested_archive() -> bytes:
    """Create a small nested ZIP archive."""
    nested = io.BytesIO()
    with zipfile.ZipFile(nested, "w") as inner:
        inner.writestr("nested.txt", b"nested")
    return nested.getvalue()


def make_symlink_entry() -> ZipEntry:
    """Create a symbolic-link ZIP member."""
    link = zipfile.ZipInfo("word/link")
    link.create_system = 3
    link.external_attr = (stat.S_IFLNK | 0o777) << 16
    return link, b"target"


def write_zip(document: bytes, entries: list[ZipEntry]) -> bytes:
    """Serialize supplied members into a small DOCX-like archive."""
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("word/document.xml", document)
        archive.writestr("word/", b"")
        archive.writestr("word/empty.bin", b"")
        for name, payload in entries:
            archive.writestr(name, payload)
    return output.getvalue()


def lie_about_declared_size(data: bytes) -> bytes:
    """Change the central-directory size without changing member contents."""
    corrupted = bytearray(data)
    position = data.find(b"PK\x01\x02")
    if position < 0:
        message = "the archive has no central directory record"
        raise AssertionError(message)
    corrupted[position + 24 : position + 28] = (1).to_bytes(4, "little")
    return bytes(corrupted)


def billion_laughs_payload() -> bytes:
    """Return an XML document whose nested entities expand exponentially."""
    declarations = ['<!ENTITY lol "lol">']
    for index in range(1, 10):
        previous = "lol" if index == 1 else f"lol{index - 1}"
        expansion = f"&{previous};" * 10
        declarations.append(f'<!ENTITY lol{index} "{expansion}">')
    document = (
        '<?xml version="1.0"?><!DOCTYPE lolz ['
        + "".join(declarations)
        + "]><lolz>&lol9;</lolz>"
    )
    return document.encode()
