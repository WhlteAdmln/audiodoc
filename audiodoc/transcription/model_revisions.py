# Copyright (c) 2026 Nikolai Zelensky
"""Pinned Hugging Face revisions of the supported Whisper models."""

import json
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Final

MODEL_REVISIONS: Final = MappingProxyType(
    {
        "tiny": "d90ca5fe260221311c53c58e660288d3deb8d356",
        "tiny.en": "0d3d19a32d3338f10357c0889762bd8d64bbdeba",
        "base": "ebe41f70d5b6dfa9166e2c581c45c9c0cfc57b66",
        "base.en": "3d3d5dee26484f91867d81cb899cfcf72b96be6c",
        "small": "536b0662742c02347bc0e980a01041f333bce120",
        "small.en": "d1d751a5f8271d482d14ca55d9e2deeebbae577f",
        "medium": "08e178d48790749d25932bbc082711ddcfdfbc4f",
        "medium.en": "a29b04bd15381511a9af671baec01072039215e3",
        "large": "edaa852ec7e145841d8ffdb056a99866b5f0a478",
        "large-v1": "b07c8d4be0be90092aa01a29c975077acb8d15c9",
        "large-v2": "f0fe81560cb8b68660e564f55dd99207059c092e",
        "large-v3": "edaa852ec7e145841d8ffdb056a99866b5f0a478",
        "distil-small.en": "ef77d90526ccd62cde3808ee70626a01e5cf83e4",
        "distil-medium.en": "80ddfce281f77766d8943d63109199fc8145dfa5",
        "distil-large-v2": "fe9b404fc56de3f7c38606ef9ba6fd83526d05e4",
        "distil-large-v3": "c3058b475261292e64a0412df1d2681c06260fab",
    }
)
REVISION_MARKER_NAME: Final = ".audiodoc-model.json"


@dataclass(frozen=True)
class InstalledModel:
    """Name and revision of a downloaded Whisper model."""

    name: str
    revision: str


def write_revision_marker(directory: Path, model: InstalledModel) -> None:
    """Record the name and revision of a downloaded model in its directory."""
    content = json.dumps({"name": model.name, "revision": model.revision})
    (directory / REVISION_MARKER_NAME).write_text(content + "\n", encoding="utf-8")


def remove_revision_marker(directory: Path) -> None:
    """Remove the revision marker of a model directory if it exists."""
    (directory / REVISION_MARKER_NAME).unlink(missing_ok=True)


def read_revision_marker(directory: Path) -> InstalledModel | None:
    """Return the recorded model, or None when the marker is missing or invalid."""
    try:
        content = json.loads(
            (directory / REVISION_MARKER_NAME).read_text(encoding="utf-8")
        )
    except (OSError, ValueError):
        return None
    if (
        isinstance(content, dict)
        and isinstance(content.get("name"), str)
        and isinstance(content.get("revision"), str)
    ):
        return InstalledModel(content["name"], content["revision"])
    return None
