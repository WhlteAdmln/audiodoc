# Copyright (c) 2026 Nikolai Zelensky
"""Эвристика определения текстовых файлов по начальному фрагменту."""


def looks_like_text(data: bytes) -> bool:
    """Возвращает True, если первые 4096 байт похожи на UTF-8 текст."""
    sample = data[:4096]

    if b"\x00" in sample:
        return False

    try:
        sample.decode("utf-8")
    except UnicodeDecodeError:
        return False
    return True
