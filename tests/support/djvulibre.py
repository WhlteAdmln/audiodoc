# Copyright (c) 2026 Nikolai Zelensky
"""Fake DjVuLibre executables that record their calls."""

import io
import json
import sys
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

_TOOLS = ("djvutxt", "djvused", "ddjvu")

_SCRIPT = """#!{python}
import json
import sys
import time
from pathlib import Path

tool = Path(__file__).name
state = Path(__file__).resolve().parent.parent / "djvulibre-state"
config = json.loads((state / "config.json").read_text(encoding="utf-8"))[tool]
args = sys.argv[1:]
document = next((arg for arg in args if arg.endswith(".djvu")), "")
call = {{"tool": tool, "args": args, "document_exists": Path(document).is_file()}}
with (state / "calls.jsonl").open("a", encoding="utf-8") as log:
    log.write(json.dumps(call) + "\\n")
time.sleep(config["delay"])
sys.stderr.write(config["stderr"])
sys.stdout.buffer.write(bytes.fromhex(config["stdout"]))
if config["page"] is not None:
    Path(args[-1]).write_bytes(bytes.fromhex(config["page"]))
sys.exit(config["exit_code"])
"""


def tiff_page() -> bytes:
    """Return a small white TIFF image, as ``ddjvu -format=tiff`` would write."""
    output = io.BytesIO()
    with Image.new("L", (6, 4), color=255) as image:
        image.save(output, format="TIFF")
    return output.getvalue()


@dataclass(frozen=True)
class ToolBehavior:
    """What one fake tool does: its output, exit code, delay and rendered page."""

    stdout: bytes = b""
    stderr: str = ""
    exit_code: int = 0
    delay: float = 0.0
    page: bytes | None = None


class FakeDjvuLibre:
    """Install DjVuLibre scripts in ``<root>/bin`` and keep their state beside them.

    Each tool records its arguments and whether the ``.djvu`` file it was given
    exists, then acts as its ``ToolBehavior`` says: it waits, writes stderr and
    stdout, writes the page (when set) to its last argument and exits. By default
    ``djvutxt`` prints a text layer, ``djvused`` reports one page and ``ddjvu``
    renders a small TIFF page.
    """

    def __init__(self, root: Path, *, tools: tuple[str, ...] = _TOOLS) -> None:
        """Write the scripts of the given tools and their default behavior."""
        self.bin_dir = root / "bin"
        self._state = root / "djvulibre-state"
        self.bin_dir.mkdir(parents=True, exist_ok=True)
        self._state.mkdir(parents=True, exist_ok=True)
        for tool in tools:
            script = self.bin_dir / tool
            script.write_text(_SCRIPT.format(python=sys.executable), encoding="utf-8")
            script.chmod(0o755)
        self._behaviors = {
            "djvutxt": ToolBehavior(stdout=b"text layer"),
            "djvused": ToolBehavior(stdout=b"1\n"),
            "ddjvu": ToolBehavior(page=tiff_page()),
        }
        self._write_config()

    def configure(self, tool: str, behavior: ToolBehavior) -> None:
        """Replace the behavior of one tool for its next calls."""
        self._behaviors[tool] = behavior
        self._write_config()

    @property
    def calls(self) -> list[dict[str, object]]:
        """Return every recorded call (tool, arguments, document presence)."""
        log = self._state / "calls.jsonl"
        if not log.exists():
            return []
        lines = log.read_text(encoding="utf-8").splitlines()
        return [json.loads(line) for line in lines]

    def arguments_of(self, tool: str) -> list[list[str]]:
        """Return the arguments of every call of one tool, oldest first."""
        log = self._state / "calls.jsonl"
        if not log.exists():
            return []
        lines = log.read_text(encoding="utf-8").splitlines()
        calls = [json.loads(line) for line in lines]
        return [call["args"] for call in calls if call["tool"] == tool]

    def _write_config(self) -> None:
        config = {
            tool: {
                "stdout": behavior.stdout.hex(),
                "stderr": behavior.stderr,
                "exit_code": behavior.exit_code,
                "delay": behavior.delay,
                "page": None if behavior.page is None else behavior.page.hex(),
            }
            for tool, behavior in self._behaviors.items()
        }
        (self._state / "config.json").write_text(json.dumps(config), encoding="utf-8")
