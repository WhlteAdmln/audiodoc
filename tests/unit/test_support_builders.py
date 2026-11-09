# Copyright (c) 2026 Nikolai Zelensky
"""Tests for shared test file builders."""

import csv
import wave
from collections.abc import Callable
from io import BytesIO, StringIO
from zipfile import ZipFile

import av
import pymupdf
import pytest
from defusedxml import ElementTree

from tests.support import builders


def test_text_builders_create_valid_content() -> None:
    assert b"TXT test" in builders.create_txt()
    assert b"# Markdown test" in builders.create_md()
    assert b"<html" in builders.create_html()
    assert b"{\\rtf1" in builders.create_rtf()

    xml_root = ElementTree.fromstring(builders.create_xml())
    assert xml_root.findtext("title") == "XML test"

    csv_rows = list(
        csv.reader(StringIO(builders.create_csv().decode("utf-8"))),
    )
    assert csv_rows == [
        ["Name", "Value"],
        ["Document engine", "Works!"],
    ]


@pytest.mark.parametrize(
    ("builder", "member"),
    [
        (builders.create_docx, "word/document.xml"),
        (builders.create_xlsx, "xl/workbook.xml"),
        (builders.create_pptx, "ppt/presentation.xml"),
        (builders.create_odt, "content.xml"),
        (builders.create_ods, "content.xml"),
        (builders.create_odp, "content.xml"),
        (builders.create_epub, "META-INF/container.xml"),
    ],
)
def test_archive_builders_create_valid_packages(
    builder: Callable[[], bytes],
    member: str,
) -> None:
    with ZipFile(BytesIO(builder())) as archive:
        assert archive.testzip() is None
        assert member in archive.namelist()


def test_fb2_builder_creates_valid_xml() -> None:
    document = ElementTree.fromstring(builders.create_fb2())
    assert "FB2 test" in "".join(document.itertext())


def test_pdf_builders_create_text_and_image_documents() -> None:
    with pymupdf.open(
        stream=builders.create_pdf(),
        filetype="pdf",
    ) as document:
        assert "PDF document test" in document[0].get_text()

    with pymupdf.open(
        stream=builders.create_image_only_pdf(),
        filetype="pdf",
    ) as document:
        page = document[0]
        assert page.get_text().strip() == ""
        assert page.get_images(full=True)

    with pymupdf.open(
        stream=builders.create_scanned_pdf(),
        filetype="pdf",
    ) as document:
        assert "normal PDF text page" in document[0].get_text()
        assert document[1].get_images(full=True)


def test_audio_builders_create_decodable_audio() -> None:
    with wave.open(BytesIO(builders.create_wav()), "rb") as audio:
        assert audio.getnchannels() == 1
        assert audio.getframerate() == 16_000
        assert audio.getnframes() > 0

    with av.open(BytesIO(builders.create_ogg_opus()), mode="r") as container:
        audio_stream = next(
            stream for stream in container.streams if stream.type == "audio"
        )
        assert audio_stream.codec_context.name == "opus"
        assert list(container.decode(audio=audio_stream.index))


def test_ocr_image_builder_creates_png_data() -> None:
    assert builders.create_ocr_image().startswith(b"\x89PNG\r\n\x1a\n")
