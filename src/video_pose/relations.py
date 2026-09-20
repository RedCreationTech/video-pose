from __future__ import annotations

from collections import defaultdict
from math import hypot

from .observations import (
    BoundingBox,
    Observation,
    ObservationType,
    Point2D,
    SpatialRelation,
)


def point_to_box_distance(point: Point2D, box: BoundingBox) -> float:
    dx = max(box.x1 - point.x, 0.0, point.x - box.x2)
    dy = max(box.y1 - point.y, 0.0, point.y - box.y2)
    return hypot(dx, dy)


class HumanObjectRelationBuilder:
    """Infer wrist-object proximity relations with temporal debouncing."""

    def __init__(
        self,
        *,
        hold_ratio: float = 0.20,
        near_ratio: float = 0.75,
        min_hold_px: float = 18.0,
        min_near_px: float = 60.0,
        hold_frames: int = 2,
        free_frames: int = 2,
        wrist_names: tuple[str, ...] = ("left_wrist", "right_wrist"),
    ) -> None:
        self.hold_ratio = hold_ratio
        self.near_ratio = near_ratio
        self.min_hold_px = min_hold_px
        self.min_near_px = min_near_px
        self.hold_frames = hold_frames
        self.free_frames = free_frames
        self.wrist_names = wrist_names
        self._hold_counts: dict[tuple[str, str, str], int] = defaultdict(int)
        self._free_counts: dict[tuple[str, str], int] = defaultdict(int)

    def enrich(self, observations: list[Observation]) -> list[Observation]:
        grouped: dict[tuple[str, float], list[Observation]] = defaultdict(list)
        for observation in observations:
            grouped[(observation.camera_id, observation.timestamp_ms)].append(
                observation
            )

        output: list[Observation] = []
        for facts in grouped.values():
            output.extend(self._enrich_frame(facts))
        return output

    def _enrich_frame(self, facts: list[Observation]) -> list[Observation]:
        if not facts:
            return []
        objects = [
            item
            for item in facts
            if item.type == ObservationType.OBJECT and item.bbox is not None
        ]
        wrists = [
            item
            for item in facts
            if item.type == ObservationType.BODY_KEYPOINT
            and item.entity_class in self.wrist_names
            and item.point_2d is not None
        ]

        output: list[Observation] = []
        for obj in objects:
            assert obj.bbox is not None
            closest = self._closest_wrist(obj.bbox, wrists)
            max_dimension = max(
                obj.bbox.x2 - obj.bbox.x1,
                obj.bbox.y2 - obj.bbox.y1,
            )
            hold_threshold = max(self.min_hold_px, max_dimension * self.hold_ratio)
            near_threshold = max(self.min_near_px, max_dimension * self.near_ratio)

            if closest is None:
                output.extend(self._mark_free(obj))
                continue

            wrist, distance = closest
            if distance <= hold_threshold:
                output.extend(self._mark_held(obj, wrist, distance, hold_threshold))
            elif distance <= near_threshold:
                self._reset_object_state(obj)
                output.append(
                    self._relation(
                        obj,
                        relation=SpatialRelation.NEAR,
                        target_id=wrist.entity_id,
                        confidence=self._relation_confidence(
                            obj,
                            wrist,
                            distance,
                            near_threshold,
                        ),
                    )
                )
            else:
                output.extend(self._mark_free(obj))
        return output

    def _closest_wrist(
        self,
        box: BoundingBox,
        wrists: list[Observation],
    ) -> tuple[Observation, float] | None:
        candidates = [
            (wrist, point_to_box_distance(wrist.point_2d, box))
            for wrist in wrists
            if wrist.point_2d is not None
        ]
        return min(candidates, key=lambda item: item[1]) if candidates else None

    def _mark_held(
        self,
        obj: Observation,
        wrist: Observation,
        distance: float,
        threshold: float,
    ) -> list[Observation]:
        key = (obj.camera_id, obj.entity_id, wrist.entity_id)
        self._hold_counts[key] += 1
        self._free_counts[(obj.camera_id, obj.entity_id)] = 0
        if self._hold_counts[key] < self.hold_frames:
            return [
                self._relation(
                    obj,
                    relation=SpatialRelation.NEAR,
                    target_id=wrist.entity_id,
                    confidence=self._relation_confidence(
                        obj,
                        wrist,
                        distance,
                        threshold,
                    ),
                )
            ]
        return [
            self._relation(
                obj,
                relation=SpatialRelation.HELD_BY,
                target_id=wrist.entity_id,
                confidence=self._relation_confidence(
                    obj,
                    wrist,
                    distance,
                    threshold,
                ),
            )
        ]

    def _mark_free(self, obj: Observation) -> list[Observation]:
        key = (obj.camera_id, obj.entity_id)
        self._free_counts[key] += 1
        for hold_key in list(self._hold_counts):
            if hold_key[:2] == key:
                self._hold_counts[hold_key] = 0
        if self._free_counts[key] < self.free_frames:
            return []
        return [
            self._relation(
                obj,
                relation=SpatialRelation.FREE,
                target_id=None,
                confidence=obj.confidence,
            )
        ]

    def _reset_object_state(self, obj: Observation) -> None:
        key = (obj.camera_id, obj.entity_id)
        self._free_counts[key] = 0
        for hold_key in list(self._hold_counts):
            if hold_key[:2] == key:
                self._hold_counts[hold_key] = 0

    def _relation(
        self,
        obj: Observation,
        *,
        relation: SpatialRelation,
        target_id: str | None,
        confidence: float,
    ) -> Observation:
        return Observation(
            observation_id=(
                f"relation:{obj.camera_id}:{obj.timestamp_ms}:"
                f"{obj.entity_id}:{relation.value}"
            ),
            session_id=obj.session_id,
            camera_id=obj.camera_id,
            timestamp_ms=obj.timestamp_ms,
            type=ObservationType.RELATION,
            entity_id=obj.entity_id,
            entity_class=obj.entity_class,
            confidence=max(0.0, min(1.0, confidence)),
            relation=relation,
            target_id=target_id,
            model_name="human-object-relation-baseline",
            model_version="0.1",
        )

    @staticmethod
    def _relation_confidence(
        obj: Observation,
        wrist: Observation,
        distance: float,
        threshold: float,
    ) -> float:
        geometry = max(0.5, 1.0 - distance / max(threshold, 1.0))
        return min(obj.confidence, wrist.confidence) * geometry
