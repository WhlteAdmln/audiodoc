"""Shared extraction context and helpers for bounded document extractors."""

from dataclasses import dataclass

from backend.common.deadline import Deadline
from backend.common.text_budget import TextBudget
from backend.document_engine.limits import (
    DOCUMENT_PROCESSING_TIMEOUT,
    MAX_EXTRACTED_TEXT_LENGTH,
)


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
