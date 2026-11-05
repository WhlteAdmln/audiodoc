"""Изолированные тесты экстракторов ODT, ODS и ODP (этап A4)."""

from backend.document_engine.extractors.odf import extract_odf
from backend.document_engine.extractors.odf.odp import extract_odp
from backend.document_engine.extractors.odf.ods import extract_ods
from backend.document_engine.extractors.odf.odt import extract_odt
from odf.opendocument import load as load_odf
import io

from tests.builders import create_odp, create_ods, create_odt


def _load(data: bytes):
    return load_odf(io.BytesIO(data))


def test_odt_extracts_headings_and_paragraphs():
    data = create_odt()
    text = extract_odf(data, "odt")

    assert text == "ODT test\nDocument engine works!"
    assert extract_odt(_load(data)) == text


def test_ods_extracts_sheet_names_and_rows():
    data = create_ods()
    text = extract_odf(data, "ods")

    assert text == ("--- Лист: Test sheet ---\nName | Value\nDocument engine | Works!")
    assert extract_ods(_load(data)) == text


def test_odp_extracts_slide_headings_and_paragraphs():
    data = create_odp()
    text = extract_odf(data, "odp")

    assert text == "--- Слайд 1 ---\nODP test\nDocument engine works!"
    assert extract_odp(_load(data)) == text


def test_unknown_odf_type_returns_empty_text():
    assert extract_odf(create_odt(), "unknown") == ""
