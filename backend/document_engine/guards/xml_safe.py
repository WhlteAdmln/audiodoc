# Copyright (c) 2026 Nikolai Zelensky
"""Parse untrusted XML while rejecting DTD and entity declarations."""

from __future__ import annotations

from typing import TYPE_CHECKING

from defusedxml import ElementTree as SafeElementTree
from defusedxml.common import DefusedXmlException

from backend.errors.documents import DocumentRejectedError

if TYPE_CHECKING:
    from xml.etree.ElementTree import Element


class _ForbiddenXmlConstructsError(DocumentRejectedError):
    """Raised when XML contains forbidden declarations."""

    public_message = "XML содержит запрещённые конструкции"


class _MalformedXmlDocumentError(DocumentRejectedError):
    """Raised when an XML document cannot be parsed."""

    public_message = "Некорректный XML-документ"


def parse_xml(data: bytes) -> Element[str]:
    """Parse XML bytes with DTD and external entity processing disabled.

    Args:
        data: Complete XML document bytes.

    Returns:
        The parsed root element.

    Raises:
        DocumentRejectedError: If DTD/entities are present or XML is malformed.

    """
    try:
        return SafeElementTree.fromstring(
            data, forbid_dtd=True, forbid_entities=True, forbid_external=True
        )
    except DefusedXmlException as error:
        raise _ForbiddenXmlConstructsError from error
    except Exception as error:
        # ElementTree parse errors and parser-level failures must not escape
        # with implementation details; the caller only needs a safe rejection.
        raise _MalformedXmlDocumentError from error
