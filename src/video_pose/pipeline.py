from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol

from .contracts import ActionEvent
from .enrichment import ObservationEnricher
from .fusion import fuse_observations
from .observations import Observation
from .perception import PerceptionAdapter
from .processing import ObservationProcessor
from .video_replay import SynchronizedFrameSet


class ActionRecognizer(Protocol):
    def ingest(self, observations: list[Observation]) -> list[ActionEvent]: ...


class VideoPosePipeline:
    """Orchestrate synchronized frames without coupling to concrete AI models."""

    def __init__(
        self,
        perception: PerceptionAdapter,
        action_recognizer: ActionRecognizer,
        *,
        observation_processors: list[ObservationProcessor] | None = None,
        observation_enrichers: list[ObservationEnricher] | None = None,
    ) -> None:
        self.perception = perception
        self.action_recognizer = action_recognizer
        self.observation_processors = observation_processors or []
        self.observation_enrichers = observation_enrichers or []

    def process(
        self,
        frame_sets: Iterable[SynchronizedFrameSet],
    ) -> list[ActionEvent]:
        actions: list[ActionEvent] = []
        for frame_set in frame_sets:
            observations = self.perception.infer(frame_set)
            for processor in self.observation_processors:
                observations = processor.process(observations)
            for enricher in self.observation_enrichers:
                observations.extend(enricher.enrich(observations))
            fused = fuse_observations(observations)
            actions.extend(self.action_recognizer.ingest(fused))
        return actions
