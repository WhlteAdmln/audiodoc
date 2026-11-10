# Copyright (c) 2026 Nikolai Zelensky
"""Shared extraction context and helpers for bounded document extractors."""

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from operator import attrgetter
from typing import cast

from audiodoc.common.deadline import Deadline
from audiodoc.common.text_budget import TextBudget
from audiodoc.document_engine.limits import (
    DOCUMENT_PROCESSING_TIMEOUT,
    MAX_EXTRACTED_TEXT_LENGTH,
)


def odf_elements(document: object, element_type: object) -> Iterable[object]:
    """Return ODF elements without depending on the library's missing stubs."""
    getter = cast(
        "Callable[[object], Iterable[object]]",
        attrgetter("getElementsByType")(document),
    )
    return getter(element_type)


def odf_attribute(element: object, name: str) -> object:
    """Read an ODF attribute without depending on the library's missing stubs."""
    getter = cast("Callable[[str], object]", attrgetter("getAttribute")(element))
    return getter(name)


@dataclass
class ExtractContext:
    """Carry the shared text budget, deadline, and source name through extraction."""

    budget: TextBudget
    deadline: Deadline
    filename: str = ""

    def check(self) -> None:
        """Raise when the document's shared processing deadline has expired."""
        self.deadline.check()


def make_context(
    context: ExtractContext | None = None,
    *,
    deadline: Deadline | None = None,
    filename: str = "",
) -> ExtractContext:
    """Return a supplied extraction context or create a backward-compatible one."""
    if context is not None:
        return context
    return ExtractContext(
        budget=TextBudget(MAX_EXTRACTED_TEXT_LENGTH),
        deadline=deadline or Deadline(DOCUMENT_PROCESSING_TIMEOUT),
        filename=filename,
    )


def add_chunk(
    chunks: list[str],
    context: ExtractContext,
    text: str,
    *,
    separator_length: int = 1,
) -> None:
    """Add a non-empty chunk if it fits the shared budget."""
    piece = context.budget.add(text, separator_length=separator_length)
    if piece:
        chunks.append(piece)
