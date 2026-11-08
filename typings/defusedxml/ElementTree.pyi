# Copyright (C) 2026

from xml.etree.ElementTree import Element

def fromstring(
    text: str | bytes,
    forbid_dtd: bool = ...,
    forbid_entities: bool = ...,
    forbid_external: bool = ...,
) -> Element[str]: ...
