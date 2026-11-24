# Copyright (c) 2026 Nikolai Zelensky
"""A fake ``tesseract`` executable that records how it is called."""

import json
import sys
from pathlib import Path

_SCRIPT = """#!{python}
import json
import shutil
import sys
import time
from pathlib import Path

state = Path(__file__).resolve().parent.parent / "tesseract-state"
config = json.loads((state / "config.json").read_text(encoding="utf-8"))
args = sys.argv[1:]
if args[:1] == ["--list-langs"]:
    with (state / "queries.log").open("a", encoding="utf-8") as log:
        log.write("query\\n")
    languages = config["languages"]
    sys.stdout.write(f"List of available languages ({{len(languages)}}):\\n")
    sys.stdout.write("".join(f"{{language}}\\n" for language in languages))
    sys.exit(config["languages_exit_code"])
calls = state / "calls.jsonl"
index = len(calls.read_text(encoding="utf-8").splitlines()) if calls.exists() else 0
shutil.copy(args[0], state / f"image_{{index}}.png")
with calls.open("a", encoding="utf-8") as log:
    log.write(json.dumps(args) + "\\n")
time.sleep(config["delay"])
sys.stderr.write(config["stderr"])
pages = config["pages"]
sys.stdout.buffer.write(bytes.fromhex(pages[min(index, len(pages) - 1)]))
sys.exit(config["exit_code"])
"""


class FakeTesseract:
    """Install a ``tesseract`` script in ``<root>/bin`` and keep its state beside it.

    The script lists the configured languages for ``--list-langs``. For a
    recognition call it copies the input image, records the arguments, waits
    ``delay`` seconds, writes ``stderr`` and prints the next of ``pages``
    (the last one repeats) before it exits with ``exit_code``.
    """

    def __init__(self, root: Path) -> None:
        """Write the script and a configuration that recognizes one page."""
        self.bin_dir = root / "bin"
        self._state = root / "tesseract-state"
        self.bin_dir.mkdir(parents=True, exist_ok=True)
        self._state.mkdir(parents=True, exist_ok=True)
        script = self.bin_dir / "tesseract"
        script.write_text(_SCRIPT.format(python=sys.executable), encoding="utf-8")
        script.chmod(0o755)
        self._config: dict[str, object] = {
            "languages": ["eng", "rus"],
            "languages_exit_code": 0,
            "pages": [b"recognized".hex()],
            "delay": 0.0,
            "stderr": "",
            "exit_code": 0,
        }
        self._write_config()

    def configure(
        self,
        *,
        languages: list[str] | None = None,
        languages_exit_code: int | None = None,
        pages: list[bytes] | None = None,
        delay: float | None = None,
        stderr: str | None = None,
        exit_code: int | None = None,
    ) -> None:
        """Change the behavior of the next calls; ``None`` keeps a setting."""
        changes = {
            "languages": languages,
            "languages_exit_code": languages_exit_code,
            "pages": None if pages is None else [page.hex() for page in pages],
            "delay": delay,
            "stderr": stderr,
            "exit_code": exit_code,
        }
        self._config.update(
            {name: value for name, value in changes.items() if value is not None}
        )
        self._write_config()

    @property
    def recognitions(self) -> list[list[str]]:
        """Return the arguments of every recognition call, oldest first."""
        calls = self._state / "calls.jsonl"
        if not calls.exists():
            return []
        lines = calls.read_text(encoding="utf-8").splitlines()
        return [json.loads(line) for line in lines]

    @property
    def language_queries(self) -> int:
        """Return how many times the language list was requested."""
        log = self._state / "queries.log"
        if not log.exists():
            return 0
        return len(log.read_text(encoding="utf-8").splitlines())

    def received_image(self, index: int) -> Path:
        """Return the copy of the image that a recognition call received."""
        return self._state / f"image_{index}.png"

    def _write_config(self) -> None:
        (self._state / "config.json").write_text(
            json.dumps(self._config), encoding="utf-8"
        )
