"""Parse untrusted XML while rejecting DTD and entity declarations."""

from xml.etree.ElementTree import Element

from defusedxml import ElementTree as SafeElementTree
from defusedxml.common import DefusedXmlException

from backend.errors.documents import DocumentRejectedError


def parse_xml(data: bytes) -> Element:
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
        raise DocumentRejectedError("XML содержит запрещённые конструкции") from error
    except Exception as error:
        # ElementTree parse errors and parser-level failures must not escape
        # with implementation details; the caller only needs a safe rejection.
        raise DocumentRejectedError("Некорректный XML-документ") from error
