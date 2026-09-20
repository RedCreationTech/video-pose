from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from .observations import Observation, ObservationType, Point2D, SpatialRelation


class Zone2D(BaseModel):
    name: str
    camera_id: str
    x1: float
    y1: float
    x2: float
    y2: float
    object_classes: set[str] = Field(default_factory=set)
    entity_types: set[ObservationType] = Field(
        default_factory=lambda: {ObservationType.OBJECT}
    )

    def contains(self, x: float, y: float) -> bool:
        return self.x1 <= x <= self.x2 and self.y1 <= y <= self.y2


class ZoneConfiguration(BaseModel):
    zones: list[Zone2D]


def load_zones(path: str | Path) -> ZoneConfiguration:
    with Path(path).open("r", encoding="utf-8") as handle:
        return ZoneConfiguration.model_validate(yaml.safe_load(handle))


class ZoneRelationBuilder:
    """MVP image-space zone mapper for objects, people and keypoints."""

    def __init__(self, zones: list[Zone2D]) -> None:
        self.zones = zones

    def enrich(self, observations: list[Observation]) -> list[Observation]:
        output: list[Observation] = []
        for observation in observations:
            point = self._point(observation)
            if point is None:
                continue
            for zone in self.zones:
                if zone.camera_id != observation.camera_id:
                    continue
                if observation.type not in zone.entity_types:
                    continue
                if (
                    zone.object_classes
                    and observation.entity_class not in zone.object_classes
                ):
                    continue
                if not zone.contains(point.x, point.y):
                    continue
                output.append(
                    Observation(
                        observation_id=(
                            f"zone:{observation.camera_id}:"
                            f"{observation.timestamp_ms}:"
                            f"{observation.entity_id}:{zone.name}"
                        ),
                        session_id=observation.session_id,
                        camera_id=observation.camera_id,
                        timestamp_ms=observation.timestamp_ms,
                        type=ObservationType.ZONE_RELATION,
                        entity_id=observation.entity_id,
                        entity_class=observation.entity_class,
                        confidence=observation.confidence,
                        relation=SpatialRelation.IN,
                        zone=zone.name,
                        model_name="zone-2d-baseline",
                        model_version="0.2",
                    )
                )
        return output

    @staticmethod
    def _point(observation: Observation) -> Point2D | None:
        if observation.point_2d is not None:
            return observation.point_2d
        if observation.bbox is None:
            return None
        return Point2D(
            x=(observation.bbox.x1 + observation.bbox.x2) / 2.0,
            y=(observation.bbox.y1 + observation.bbox.y2) / 2.0,
        )
