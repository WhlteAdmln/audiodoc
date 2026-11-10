# Copyright (c) 2026 Nikolai Zelensky
"""Supported Document Engine formats and extensions."""

SUPPORTED_FORMATS = {
    "pdf",
    "doc",
    "docx",
    "xls",
    "xlsx",
    "ppt",
    "pptx",
    "odt",
    "ods",
    "odp",
    "epub",
    "fb2",
    "djvu",
    "txt",
    "md",
    "rtf",
    "html",
    "xml",
    "csv",
}

IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".tif",
    ".tiff",
    ".bmp",
    ".webp",
    ".gif",
}

extension_map = {
    "txt": "txt",
    "md": "md",
    "markdown": "md",
    "html": "html",
    "htm": "html",
    "xml": "xml",
    "csv": "csv",
    "fb2": "fb2",
    "rtf": "rtf",
    "doc": "doc",
    "xls": "xls",
    "ppt": "ppt",
    "djvu": "djvu",
    "djv": "djvu",
}
