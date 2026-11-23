# Copyright (c) 2026 Nikolai Zelensky
"""Matrix of document formats with builders for extractor tests."""

from collections.abc import Callable

from tests.support.builders import (
    create_csv,
    create_djvu,
    create_docx,
    create_epub,
    create_fb2,
    create_html,
    create_md,
    create_odp,
    create_ods,
    create_odt,
    create_pdf,
    create_pptx,
    create_rtf,
    create_txt,
    create_xlsx,
    create_xml,
)

Builder = Callable[[], bytes]


MATRIX: tuple[tuple[str, str, Builder, str], ...] = (
    ("pdf", ".pdf", create_pdf, "PDF document test"),
    ("docx", ".docx", create_docx, "DOCX test"),
    ("xlsx", ".xlsx", create_xlsx, "Document engine"),
    ("pptx", ".pptx", create_pptx, "PPTX test"),
    ("epub", ".epub", create_epub, "EPUB test"),
    ("fb2", ".fb2", create_fb2, "FB2 test"),
    ("djvu", ".djvu", create_djvu, "DJVU text layer"),
    ("odt", ".odt", create_odt, "ODT test"),
    ("ods", ".ods", create_ods, "Document engine"),
    ("odp", ".odp", create_odp, "ODP test"),
    ("txt", ".txt", create_txt, "TXT test"),
    ("md", ".md", create_md, "Markdown test"),
    ("csv", ".csv", create_csv, "Document engine"),
    ("html", ".html", create_html, "HTML test"),
    ("xml", ".xml", create_xml, "XML test"),
    ("rtf", ".rtf", create_rtf, "RTF test"),
)
