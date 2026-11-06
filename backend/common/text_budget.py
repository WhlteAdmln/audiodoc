"""Count extracted text incrementally so large documents stop early.

The budget accounts for the separator inserted between accepted chunks and
never allows the final joined text to exceed its configured character limit.
"""


class TextBudget:
    """A monotonic character budget for one document extraction operation."""

    def __init__(self, limit: int) -> None:
        """Create a budget with a positive maximum number of output characters."""
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
            raise ValueError("limit must be a positive integer")
        self.limit = limit
        self.used = 0
        self._has_content = False
        self._truncated = False

    @property
    def exhausted(self) -> bool:
        """Whether no additional character can be accepted."""
        return self.used >= self.limit

    @property
    def truncated(self) -> bool:
        """Whether extracted content was omitted because of an output limit."""
        return self._truncated

    def mark_truncated(self) -> None:
        """Mark output incomplete when extraction stops while source input remains."""
        self._truncated = True

    def add(self, text: str, *, separator_length: int = 1) -> str:
        """Accept a chunk, returning its possibly truncated text.

        Args:
            text: Next text chunk to append to the accumulated result.
            separator_length: Number of characters used to separate this chunk
                from the previous non-empty chunk (default: one newline).

        Returns:
            The accepted part of ``text``. Join accepted chunks with a
            separator of the same length to produce a string within the limit.
        """
        if not isinstance(text, str):
            raise TypeError("text must be a string")
        if (
            isinstance(separator_length, bool)
            or not isinstance(separator_length, int)
            or separator_length < 0
        ):
            raise ValueError("separator_length must be a non-negative integer")
        if not text:
            return ""
        if self.exhausted:
            self._truncated = True
            return ""

        separator = separator_length if self._has_content else 0
        remaining = self.limit - self.used - separator
        if remaining <= 0:
            self._truncated = True
            self.used = self.limit
            return ""

        piece = text[:remaining]
        self.used += separator + len(piece)
        self._has_content = self._has_content or bool(piece)
        if len(piece) < len(text):
            self._truncated = True
        return piece
