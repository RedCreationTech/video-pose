from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .video_replay import FrameRef


@dataclass(frozen=True, slots=True)
class DecodedFrame:
    ref: FrameRef
    image: Any
