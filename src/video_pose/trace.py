from __future__ import annotations

from dataclasses import dataclass

from .contracts import ActionEvent
from .observations import Observation
from .video_replay import SynchronizedFrameSet


@dataclass(frozen=True, slots=True)
class FrameTrace:
    frame_set: SynchronizedFrameSet
    observations: tuple[Observation, ...]
    actions: tuple[ActionEvent, ...]
