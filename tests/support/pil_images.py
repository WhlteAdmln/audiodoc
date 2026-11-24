# Copyright (c) 2026 Nikolai Zelensky
"""Fake Pillow images for OCR page recognition tests."""

from typing import Never


class UnexpectedImageCopyError(AssertionError):
    """Raised when OCR copies an oversized image frame."""

    def __init__(self) -> None:
        """Initialize the test assertion error."""
        super().__init__("copy must not be called for oversized frames")


class FakePreparedImage:
    """Remember whether the prepared OCR image was closed."""

    def __init__(self) -> None:
        """Start open."""
        self.closed = False

    def close(self) -> None:
        """Mark the image as closed."""
        self.closed = True


class FakeMultiPageImage:
    """Describe a small image with several frames that can be copied."""

    def __init__(self, n_frames: int) -> None:
        """Store the number of frames of a 10 by 10 pixel image."""
        self.n_frames = n_frames
        self.width = 10
        self.height = 10
        self.current_page: object = None

    def seek(self, page: object) -> None:
        """Remember the selected frame."""
        self.current_page = page

    @staticmethod
    def copy() -> object:
        """Return a stand-in for the copied frame."""
        return object()


class OversizedImage:
    """Describe a one-frame 100 by 100 pixel image that must not be copied."""

    n_frames = 1
    width = 100
    height = 100

    @staticmethod
    def seek(_index: object) -> None:
        """Accept any frame index."""
        return

    @staticmethod
    def copy() -> Never:
        """Fail because an oversized frame must be rejected before the copy."""
        raise UnexpectedImageCopyError
