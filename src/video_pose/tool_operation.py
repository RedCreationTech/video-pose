from __future__ import annotations

from dataclasses import dataclass
from math import sqrt

from .contracts import ActionEvent, ActionObject, ActionType
from .observations import Observation, ObservationType, Point3D, SpatialRelation


@dataclass(slots=True)
class _ToolState:
    held: bool = False
    zone: str | None = None
    previous_point: Point3D | None = None
    path_length: float = 0.0
    emitted: bool = False


def _distance(left: Point3D, right: Point3D) -> float:
    return sqrt(
        (left.x - right.x) ** 2
        + (left.y - right.y) ** 2
        + (left.z - right.z) ** 2
    )


class ToolOperationRecognizer:
    """Emit OPERATE_TOOL after a held tool moves enough inside a work zone."""

    def __init__(
        self,
        session_id: str,
        *,
        tool_classes: set[str],
        operation_zones: set[str] | None = None,
        min_path_length: float = 40.0,
        min_confidence: float = 0.75,
    ) -> None:
        self.session_id = session_id
        self.tool_classes = tool_classes
        self.operation_zones = operation_zones
        self.min_path_length = min_path_length
        self.min_confidence = min_confidence
        self._states: dict[str, _ToolState] = {}
        self._sequence = 0

    def ingest(self, observations: list[Observation]) -> list[ActionEvent]:
        by_entity: dict[str, list[Observation]] = {}
        for observation in observations:
            if observation.entity_class not in self.tool_classes:
                continue
            by_entity.setdefault(observation.entity_id, []).append(observation)

        output: list[ActionEvent] = []
        for entity_id, facts in by_entity.items():
            state = self._states.setdefault(entity_id, _ToolState())
            held = any(
                fact.type == ObservationType.RELATION
                and fact.relation == SpatialRelation.HELD_BY
                and fact.confidence >= self.min_confidence
                for fact in facts
            )
            free = any(
                fact.type == ObservationType.RELATION
                and fact.relation == SpatialRelation.FREE
                for fact in facts
            )
            zone_fact = max(
                (
                    fact
                    for fact in facts
                    if fact.type == ObservationType.ZONE_RELATION
                    and fact.relation == SpatialRelation.IN
                    and fact.zone is not None
                ),
                key=lambda fact: fact.confidence,
                default=None,
            )
            point_fact = max(
                (
                    fact
                    for fact in facts
                    if fact.point_3d is not None
                    and fact.type == ObservationType.OBJECT
                ),
                key=lambda fact: fact.confidence,
                default=None,
            )

            if zone_fact is not None:
                state.zone = zone_fact.zone
            if free:
                state.held = False
                state.previous_point = None
                state.path_length = 0.0
                state.emitted = False
                continue
            if held:
                state.held = True

            if not state.held or point_fact is None or point_fact.point_3d is None:
                continue
            if (
                self.operation_zones is not None
                and state.zone not in self.operation_zones
            ):
                continue

            current_point = point_fact.point_3d
            if state.previous_point is not None:
                state.path_length += _distance(
                    state.previous_point,
                    current_point,
                )
            state.previous_point = current_point

            if state.path_length < self.min_path_length or state.emitted:
                continue
            state.emitted = True
            self._sequence += 1
            timestamp = max(0, round(point_fact.timestamp_ms))
            output.append(
                ActionEvent(
                    event_id=f"tool-operation-{self._sequence}",
                    session_id=self.session_id,
                    sequence=self._sequence,
                    action=ActionType.OPERATE_TOOL,
                    object=ActionObject(
                        id=entity_id,
                        **{"class": point_fact.entity_class},
                    ),
                    target_zone=state.zone,
                    started_at_ms=timestamp,
                    ended_at_ms=timestamp,
                    confidence=point_fact.confidence,
                    model_version="tool-operation-geometry-0.1",
                )
            )
        return output
