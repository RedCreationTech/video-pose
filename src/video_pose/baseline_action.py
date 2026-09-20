from __future__ import annotations

from dataclasses import dataclass

from .contracts import ActionEvent, ActionObject, ActionType
from .observations import Observation, SpatialRelation


@dataclass(slots=True)
class _ObjectState:
    held: bool | None = None
    zone: str | None = None
    entity_class: str | None = None


class PickPlaceActionRecognizer:
    """Explainable baseline recognizer based on relation-state transitions.

    It deliberately recognizes only actions that can be derived reliably from
    explicit object relations. More complex actions should be provided by a
    temporal model behind the same ActionEvent contract.
    """

    def __init__(self, session_id: str, min_confidence: float = 0.75) -> None:
        self.session_id = session_id
        self.min_confidence = min_confidence
        self._objects: dict[str, _ObjectState] = {}
        self._sequence = 0

    def ingest(self, observations: list[Observation]) -> list[ActionEvent]:
        grouped: dict[str, list[Observation]] = {}
        for observation in observations:
            if observation.session_id != self.session_id:
                raise ValueError("observation belongs to another session")
            if observation.confidence < self.min_confidence:
                continue
            grouped.setdefault(observation.entity_id, []).append(observation)

        events: list[ActionEvent] = []
        for entity_id, facts in grouped.items():
            event = self._update_object(entity_id, facts)
            if event is not None:
                events.append(event)
        return events

    def _update_object(
        self,
        entity_id: str,
        facts: list[Observation],
    ) -> ActionEvent | None:
        state = self._objects.setdefault(entity_id, _ObjectState())
        previous_held = state.held
        previous_zone = state.zone

        entity_class = next(
            (fact.entity_class for fact in facts if fact.entity_class is not None),
            state.entity_class,
        )
        zone_fact = max(
            (
                fact
                for fact in facts
                if fact.relation == SpatialRelation.IN and fact.zone is not None
            ),
            key=lambda item: item.confidence,
            default=None,
        )
        held_fact = max(
            (fact for fact in facts if fact.relation == SpatialRelation.HELD_BY),
            key=lambda item: item.confidence,
            default=None,
        )
        free_fact = max(
            (fact for fact in facts if fact.relation == SpatialRelation.FREE),
            key=lambda item: item.confidence,
            default=None,
        )

        if entity_class is not None:
            state.entity_class = entity_class
        if zone_fact is not None:
            state.zone = zone_fact.zone

        if held_fact is not None and (
            free_fact is None or held_fact.confidence >= free_fact.confidence
        ):
            state.held = True
        elif free_fact is not None:
            state.held = False

        if previous_held is False and state.held is True and held_fact is not None:
            return self._build_event(
                action=ActionType.PICK,
                entity_id=entity_id,
                entity_class=state.entity_class,
                timestamp_ms=held_fact.timestamp_ms,
                confidence=held_fact.confidence,
                source_zone=previous_zone,
                target_zone=None,
                hand=held_fact.target_id,
                evidence=held_fact,
            )

        if previous_held is True and state.held is False and free_fact is not None:
            confidence = free_fact.confidence
            if zone_fact is not None:
                confidence = min(confidence, zone_fact.confidence)
            return self._build_event(
                action=ActionType.PLACE,
                entity_id=entity_id,
                entity_class=state.entity_class,
                timestamp_ms=free_fact.timestamp_ms,
                confidence=confidence,
                source_zone=previous_zone,
                target_zone=state.zone,
                hand=None,
                evidence=free_fact,
            )

        return None

    def _build_event(
        self,
        *,
        action: ActionType,
        entity_id: str,
        entity_class: str | None,
        timestamp_ms: float,
        confidence: float,
        source_zone: str | None,
        target_zone: str | None,
        hand: str | None,
        evidence: Observation,
    ) -> ActionEvent:
        self._sequence += 1
        timestamp = max(0, round(timestamp_ms))
        return ActionEvent(
            event_id=f"baseline-{self._sequence}",
            session_id=self.session_id,
            sequence=self._sequence,
            action=action,
            hand=hand,
            object=ActionObject(id=entity_id, **{"class": entity_class}),
            source_zone=source_zone,
            target_zone=target_zone,
            started_at_ms=timestamp,
            ended_at_ms=timestamp,
            confidence=confidence,
            evidence_refs=[
                (
                    f"observation://{evidence.camera_id}/"
                    f"{evidence.observation_id}"
                )
            ],
            model_version="baseline-pick-place-0.1",
        )
