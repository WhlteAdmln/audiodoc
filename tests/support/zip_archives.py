# Copyright (c) 2026 Nikolai Zelensky
"""Build ZIP archives whose central directory lies about member sizes."""

import io
import struct
import zipfile
from dataclasses import dataclass

_CENTRAL_HEADER = b"PK\x01\x02"
_COMPRESSED_SIZE_OFFSET = 20


@dataclass(frozen=True)
class ZipMember:
    """Describe one archive member and the sizes its central record declares."""

    name: str
    data: bytes
    compression: int = zipfile.ZIP_STORED
    declared_file_size: int | None = None
    declared_compress_size: int | None = None


def lying_zip(members: list[ZipMember]) -> bytes:
    """Return a ZIP archive whose central records carry the declared sizes."""
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        for member in members:
            archive.writestr(member.name, member.data, compress_type=member.compression)
    payload = bytearray(output.getvalue())
    position = payload.find(_CENTRAL_HEADER)
    for member in members:
        sizes_at = position + _COMPRESSED_SIZE_OFFSET
        compress_size, file_size = struct.unpack_from("<II", payload, sizes_at)
        if member.declared_compress_size is not None:
            compress_size = member.declared_compress_size
        if member.declared_file_size is not None:
            file_size = member.declared_file_size
        struct.pack_into("<II", payload, sizes_at, compress_size, file_size)
        position = payload.find(_CENTRAL_HEADER, position + len(_CENTRAL_HEADER))
    return bytes(payload)
