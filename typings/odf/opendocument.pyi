# Copyright (c) 2026 Nikolai Zelensky

from typing import BinaryIO

class OpenDocument: ...

def load(odffile: str | BinaryIO) -> OpenDocument: ...
