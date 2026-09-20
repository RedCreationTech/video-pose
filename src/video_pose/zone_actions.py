from __future__ import annotations

from .contracts import ActionEvent, ActionType
from .observations import Observation, ObservationType, SpatialRelation


class ZoneTransitionRecognizer:
    """Emit ENTER_ZONE/LEAVE_ZONE from stable entity-zone state changes."""

    def __init__(
        self,
        session_id: str,
        *,
        entity_classes: set[str] | None = None,
    ) -> None:
        self.session_id = session_id
        self.entity_classes = entity_classes
        self._active: set[tuple[str, str]] = set()
        self._sequence = 0

    def ingest(self, observations: list[Observation]) -> list[ActionEvent]:
        current = {
            (item.entity_id, item.zone)
            for item in observations
            if item.type == ObservationType.ZONE_RELATION
            and item.relation == SpatialRelation.IN
            and item.zone is not None
            and (
                self.entity_classes is None
                or item.entity_class in self.entity_classes
            )
        }
        entered = current - self._active
        left = self._active - current
        self._active = current

        by_key = {
            (item.entity_id, item.zone): item
            for item in observations
            if item.type == ObservationType.ZONE_RELATION
            and item.zone is not None
        }
        timestamp = min(
            (item.timestamp_ms for item in observations),
            default=0.0,
        )

        events: list[ActionEvent] = []
        for entity_id, zone in sorted(entered):
            observation = by_key[(entity_id, zone)]
            events.append(
                self._event(
                    action=ActionType.ENTER_ZONE,
                    entity_id=entity_id,
                    zone=zone,
                    timestamp_ms=observation.timestamp_ms,
                    confidence=observation.confidence,
                )
            )
        for entity_id, zone in sorted(left):
            events.append(
                self._event(
                    action=ActionType.LEAVE_ZONE,
                    entity_id=entity_id,
                    zone=zone,
                    timestamp_ms=timestamp,
                    confidence=1.0,
                )
            )
        return events

    def _event(
        self,
        *,
        action: ActionType,
        entity_id: str,
        zone: str,
        timestamp_ms: float,
        confidence: float,
    ) -> ActionEvent:
        self._sequence += 1
        timestamp = max(0, round(timestamp_ms))
        return ActionEvent(
            event_id=f"zone-{self._sequence}",
            session_id=self.session_id,
            sequence=self._sequence,
            action=action,
            actor_id=entity_id,
            target_zone=zone,
            started_at_ms=timestamp,
            ended_at_ms=timestamp,
            confidence=confidence,
            model_version="zone-transition-0.1",
        )
