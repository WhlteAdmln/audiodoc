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
from PIL import ImageFont

from tests.support import builders


@pytest.mark.parametrize(
    ("builder", "marker"),
    [
        (builders.create_txt, b"TXT test"),
        (builders.create_md, b"# Markdown test"),
        (builders.create_html, b"<html"),
        (builders.create_rtf, b"{\\rtf1"),
    ],
)
def test_text_builders_create_valid_content(
    builder: Callable[[], bytes],
    marker: bytes,
) -> None:
    assert marker in builder(), "the text document lacks its marker content"


def test_xml_builder_creates_titled_document() -> None:
    xml_root = ElementTree.fromstring(builders.create_xml())

    expected_findtext = "XML test"
    assert xml_root.findtext("title") == expected_findtext, "wrong XML title"


def test_csv_builder_creates_header_and_data_row() -> None:
    csv_rows = list(
        csv.reader(StringIO(builders.create_csv().decode("utf-8"))),
    )

    expected_rows = [
        ["Name", "Value"],
        ["Document engine", "Works!"],
    ]
    assert csv_rows == expected_rows, "wrong CSV rows"


@pytest.mark.parametrize(
    "builder",
    [
        builders.create_docx,
        builders.create_xlsx,
        builders.create_pptx,
        builders.create_odt,
        builders.create_ods,
        builders.create_odp,
        builders.create_epub,
    ],
)
def test_archive_builders_create_intact_zip_archives(
    builder: Callable[[], bytes],
) -> None:
    with ZipFile(BytesIO(builder())) as archive:
        assert archive.testzip() is None, "the archive has a corrupt member"


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
        assert member in archive.namelist(), "the package lacks its main member"


def test_fb2_builder_creates_valid_xml() -> None:
    document = ElementTree.fromstring(builders.create_fb2())
    book_title = "FB2 test"
    assert book_title in "".join(document.itertext()), "the FB2 title is missing"


def test_pdf_builder_creates_text_document() -> None:
    with pymupdf.open(stream=builders.create_pdf(), filetype="pdf") as document:
        text = document[0].get_text()

    text_page = "PDF document test"
    assert text_page in text, "the PDF page lacks its text"


def test_image_only_pdf_builder_creates_page_without_text() -> None:
    with pymupdf.open(
        stream=builders.create_image_only_pdf(),
        filetype="pdf",
    ) as document:
        text = document[0].get_text().strip()

    expected_empty = ""
    assert text == expected_empty, "the image-only PDF page has text"


def test_image_only_pdf_builder_creates_page_with_image() -> None:
    with pymupdf.open(
        stream=builders.create_image_only_pdf(),
        filetype="pdf",
    ) as document:
        images = document[0].get_images(full=True)

    assert images, "the image-only PDF page has no image"


def test_scanned_pdf_builder_creates_text_first_page() -> None:
    with pymupdf.open(
        stream=builders.create_scanned_pdf(),
        filetype="pdf",
    ) as document:
        text = document[0].get_text()

    normal_page = "normal PDF text page"
    assert normal_page in text, "the first scanned PDF page lacks its text"


def test_scanned_pdf_builder_creates_image_second_page() -> None:
    with pymupdf.open(
        stream=builders.create_scanned_pdf(),
        filetype="pdf",
    ) as document:
        images = document[1].get_images(full=True)

    assert images, "the second scanned PDF page has no image"


def test_wav_builder_creates_non_empty_mono_16_khz_audio() -> None:
    with wave.open(BytesIO(builders.create_wav()), "rb") as audio:
        actual = (audio.getnchannels(), audio.getframerate(), audio.getnframes() > 0)

    expected = (1, 16_000, True)
    assert actual == expected, "wrong WAV channels, frame rate or frame count"


def test_ogg_opus_builder_creates_opus_stream() -> None:
    expected_type = "audio"
    with av.open(BytesIO(builders.create_ogg_opus()), mode="r") as container:
        codec_names = [
            stream.codec_context.name
            for stream in container.streams
            if stream.type == expected_type
        ]

    expected_names = ["opus"]
    assert codec_names == expected_names, "the OGG file has no single Opus stream"


def test_ogg_opus_builder_creates_decodable_audio() -> None:
    with av.open(BytesIO(builders.create_ogg_opus()), mode="r") as container:
        expected_type = "audio"
        audio_stream = next(
            stream for stream in container.streams if stream.type == expected_type
        )
        frames = list(container.decode(audio=audio_stream.index))

    assert frames, "the Opus stream decodes to no frames"


def test_ocr_image_builder_creates_png_data() -> None:
    png_signature = b"\x89PNG\r\n\x1a\n"
    assert builders.create_ocr_image().startswith(png_signature), "not a PNG image"


def test_ocr_image_builder_uses_large_fallback_font(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requested_sizes: list[float | None] = []
    original_load_default = ImageFont.load_default
    original_truetype = ImageFont.truetype

    def reject_dejavu(
        font: str | BytesIO,
        size: int,
        *,
        layout_engine: ImageFont.Layout | None = None,
    ) -> ImageFont.FreeTypeFont:
        if isinstance(font, str):
            message = "DejaVuSans is unavailable"
            raise OSError(message)
        return original_truetype(font, size, layout_engine=layout_engine)

    def record_load_default(
        size: float | None = None,
    ) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        requested_sizes.append(size)
        return original_load_default(size=size)

    monkeypatch.setattr(ImageFont, "truetype", reject_dejavu)
    monkeypatch.setattr(ImageFont, "load_default", record_load_default)

    builders.create_ocr_image()

    expected_sizes = [48]
    assert requested_sizes == expected_sizes, "the fallback font is not size 48"
