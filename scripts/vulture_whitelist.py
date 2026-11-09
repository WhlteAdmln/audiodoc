# Copyright (c) 2026 Nikolai Zelensky
"""Vulture whitelist for symbols accessed indirectly."""

from typing import IO

from pptx.shapes.autoshape import Shape
from pptx.shapes.graphfrm import GraphicFrame

audio: object = None
beam_size: object = None
vad_filter: object = None

_WHITELISTED_NAMES = (IO, Shape, GraphicFrame, audio, beam_size, vad_filter)
