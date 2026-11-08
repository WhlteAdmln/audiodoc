"""Small document factories for Document Engine tests.

All functions return bytes so callers can create files
in an isolated pytest temporary directory (tmp_path).
"""

import tempfile
from importlib import import_module
from io import BytesIO
from pathlib import Path


def create_docx() -> bytes:
    docx = import_module("docx")
    document = docx.Document()
    document.add_heading("DOCX test", level=1)
    document.add_paragraph("Document engine works!")
    table = document.add_table(rows=1, cols=2)
    table.cell(0, 0).text = "Name"
    table.cell(0, 1).text = "Value"

    output = BytesIO()
    document.save(output)
    return output.getvalue()


def create_xlsx() -> bytes:
    openpyxl = import_module("openpyxl")
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Test sheet"
    sheet.append(["Name", "Value"])
    sheet.append(["Document engine", "Works!"])

    output = BytesIO()
    workbook.save(output)
    return output.getvalue()


def create_pptx() -> bytes:
    pptx = import_module("pptx")
    presentation = pptx.Presentation()
    slide = presentation.slides.add_slide(presentation.slide_layouts[1])
    slide.shapes.title.text = "PPTX test"
    slide.placeholders[1].text = "Document engine works!"

    output = BytesIO()
    presentation.save(output)
    return output.getvalue()


def create_epub() -> bytes:
    epub = import_module("ebooklib.epub")
    book = epub.EpubBook()
    book.set_identifier("test-document")
    book.set_title("EPUB test")
    book.set_language("en")

    chapter = epub.EpubHtml(
        title="Chapter 1",
        file_name="chapter1.xhtml",
        lang="en",
    )
    chapter.content = "<h1>EPUB test</h1><p>Document engine works!</p>"
    book.add_item(chapter)
    book.spine = ["nav", chapter]
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "test.epub"
        epub.write_epub(str(path), book)
        return path.read_bytes()


def create_fb2() -> bytes:
    """Создаёт небольшую FictionBook 2-книгу для тестов."""
    return (
        b'<?xml version="1.0" encoding="utf-8"?>'
        b'<FictionBook xmlns="http://www.gribuser.ru/xml/fictionbook/2.0">'
        b"<description><title-info><book-title>FB2 test</book-title>"
        b"</title-info></description>"
        b"<body><section><title><p>FB2 test</p></title>"
        b"<p>Document engine works!</p>"
        b"<p>Text <emphasis>with emphasis</emphasis> preserved.</p>"
        b"</section></body></FictionBook>"
    )


def create_pdf() -> bytes:
    pymupdf = import_module("pymupdf")

    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 72), "PDF document test")
    data = document.tobytes()
    document.close()
    return data


def create_odt() -> bytes:
    odf_opendocument = import_module("odf.opendocument")
    odf_text = import_module("odf.text")

    document = odf_opendocument.OpenDocumentText()
    document.text.addElement(odf_text.H(outlinelevel=1, text="ODT test"))
    document.text.addElement(odf_text.P(text="Document engine works!"))
    output = BytesIO()
    document.save(output)
    return output.getvalue()


def create_ods() -> bytes:
    odf_opendocument = import_module("odf.opendocument")
    odf_table = import_module("odf.table")
    odf_text = import_module("odf.text")

    document = odf_opendocument.OpenDocumentSpreadsheet()
    table = odf_table.Table(name="Test sheet")
    for values in (("Name", "Value"), ("Document engine", "Works!")):
        row = odf_table.TableRow()
        for value in values:
            cell = odf_table.TableCell()
            cell.addElement(odf_text.P(text=value))
            row.addElement(cell)
        table.addElement(row)
    document.spreadsheet.addElement(table)

    output = BytesIO()
    document.save(output)
    return output.getvalue()


def create_odp() -> bytes:
    odf_draw = import_module("odf.draw")
    odf_opendocument = import_module("odf.opendocument")
    odf_style = import_module("odf.style")
    odf_text = import_module("odf.text")

    document = odf_opendocument.OpenDocumentPresentation()
    frame_style = odf_style.Style(name="FrameStyle", family="graphic")
    document.automaticstyles.addElement(frame_style)

    page = odf_draw.Page(name="Slide 1", masterpagename="Default")
    frame = odf_draw.Frame(
        stylename=frame_style,
        width="15cm",
        height="5cm",
        x="1cm",
        y="1cm",
    )
    textbox = odf_draw.TextBox()
    textbox.addElement(odf_text.P(text="ODP test"))
    textbox.addElement(odf_text.P(text="Document engine works!"))
    frame.addElement(textbox)
    page.addElement(frame)
    document.presentation.addElement(page)

    output = BytesIO()
    document.save(output)
    return output.getvalue()


def create_scanned_pdf() -> bytes:
    """Create a PDF with a text page and a page for OCR."""
    pymupdf = import_module("pymupdf")
    image_module = import_module("PIL.Image")
    image_draw_module = import_module("PIL.ImageDraw")
    image_font_module = import_module("PIL.ImageFont")

    image = image_module.new("RGB", (1200, 400), "white")
    draw = image_draw_module.Draw(image)
    try:
        font = image_font_module.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            48,
        )
    except OSError:
        font = image_font_module.load_default()
    draw.text((50, 70), "Scanned PDF OCR Test", fill="black", font=font)
    draw.text(
        (50, 170),
        "This page has no text layer.",
        fill="black",
        font=font,
    )

    image_data = BytesIO()
    image.save(image_data, format="PNG")

    document = pymupdf.open()
    text_page = document.new_page()
    text_page.insert_text(
        (72, 100),
        "This is a normal PDF text page.",
        fontsize=18,
    )
    image_page = document.new_page()
    image_page.insert_image(image_page.rect, stream=image_data.getvalue())
    data = document.tobytes()
    document.close()
    image.close()
    return data


def create_ocr_image() -> bytes:
    image_module = import_module("PIL.Image")
    image_draw_module = import_module("PIL.ImageDraw")
    image_font_module = import_module("PIL.ImageFont")

    image = image_module.new("RGB", (1200, 400), "white")
    draw = image_draw_module.Draw(image)
    try:
        font = image_font_module.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            48,
        )
    except OSError:
        font = image_font_module.load_default()
    draw.text((50, 70), "Document Engine OCR Test", fill="black", font=font)
    draw.text((50, 170), "Hello! This is a test.", fill="black", font=font)
    output = BytesIO()
    image.save(output, format="PNG")
    image.close()
    return output.getvalue()
