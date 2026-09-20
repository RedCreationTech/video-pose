from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol

from .contracts import ActionEvent
from .fusion import fuse_observations
from .observations import Observation
from .perception import PerceptionAdapter
from .video_replay import SynchronizedFrameSet


class ActionRecognizer(Protocol):
    def ingest(self, observations: list[Observation]) -> list[ActionEvent]: ...


class VideoPosePipeline:
    """Orchestrate synchronized frames without coupling to a concrete model."""

    def __init__(
        self,
        perception: PerceptionAdapter,
        action_recognizer: ActionRecognizer,
    ) -> None:
        self.perception = perception
        self.action_recognizer = action_recognizer

    def process(
        self,
        frame_sets: Iterable[SynchronizedFrameSet],
    ) -> list[ActionEvent]:
        actions: list[ActionEvent] = []
        for frame_set in frame_sets:
            observations = self.perception.infer(frame_set)
            fused = fuse_observations(observations)
            actions.extend(self.action_recognizer.ingest(fused))
        return actions
