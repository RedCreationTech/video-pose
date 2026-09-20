from __future__ import annotations

from collections import defaultdict

from .contracts import ActionEvent, ActionType
from .observations import Observation, ObservationType, SpatialRelation


class DwellZoneActionRecognizer:
    """Emit an action when selected entities remain in a zone for N frames."""

    def __init__(
        self,
        session_id: str,
        *,
        action: ActionType,
        zones: set[str],
        entity_classes: set[str] | None = None,
        dwell_frames: int = 5,
        min_confidence: float = 0.75,
    ) -> None:
        if dwell_frames < 1:
            raise ValueError("dwell_frames must be >= 1")
        self.session_id = session_id
        self.action = action
        self.zones = zones
        self.entity_classes = entity_classes
        self.dwell_frames = dwell_frames
        self.min_confidence = min_confidence
        self._counts: dict[tuple[str, str], int] = defaultdict(int)
        self._emitted: set[tuple[str, str]] = set()
        self._sequence = 0

    def ingest(self, observations: list[Observation]) -> list[ActionEvent]:
        active: dict[tuple[str, str], Observation] = {}
        for observation in observations:
            if observation.type != ObservationType.ZONE_RELATION:
                continue
            if observation.relation != SpatialRelation.IN:
                continue
            if observation.zone not in self.zones:
                continue
            if observation.confidence < self.min_confidence:
                continue
            if (
                self.entity_classes is not None
                and observation.entity_class not in self.entity_classes
            ):
                continue
            assert observation.zone is not None
            active[(observation.entity_id, observation.zone)] = observation

        known = set(self._counts) | set(active)
        output: list[ActionEvent] = []
        for key in known:
            if key not in active:
                self._counts[key] = 0
                self._emitted.discard(key)
                continue

            self._counts[key] += 1
            if self._counts[key] < self.dwell_frames or key in self._emitted:
                continue
            self._emitted.add(key)
            observation = active[key]
            self._sequence += 1
            timestamp = max(0, round(observation.timestamp_ms))
            output.append(
                ActionEvent(
                    event_id=f"dwell-{self._sequence}",
                    session_id=self.session_id,
                    sequence=self._sequence,
                    action=self.action,
                    actor_id=observation.entity_id,
                    target_zone=observation.zone,
                    started_at_ms=timestamp,
                    ended_at_ms=timestamp,
                    confidence=observation.confidence,
                    model_version="zone-dwell-0.1",
                )
            )
        return output
