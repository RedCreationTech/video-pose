from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from .observations import Observation, ObservationType, SpatialRelation


class Zone2D(BaseModel):
    name: str
    camera_id: str
    x1: float
    y1: float
    x2: float
    y2: float
    object_classes: set[str] = Field(default_factory=set)

    def contains(self, x: float, y: float) -> bool:
        return self.x1 <= x <= self.x2 and self.y1 <= y <= self.y2


class ZoneConfiguration(BaseModel):
    zones: list[Zone2D]


def load_zones(path: str | Path) -> ZoneConfiguration:
    with Path(path).open("r", encoding="utf-8") as handle:
        return ZoneConfiguration.model_validate(yaml.safe_load(handle))


class ZoneRelationBuilder:
    """MVP image-space zone mapper. World-space zones replace this in C03."""

    def __init__(self, zones: list[Zone2D]) -> None:
        self.zones = zones

    def enrich(self, observations: list[Observation]) -> list[Observation]:
        output: list[Observation] = []
        for obj in observations:
            if obj.type != ObservationType.OBJECT or obj.bbox is None:
                continue
            center_x = (obj.bbox.x1 + obj.bbox.x2) / 2.0
            center_y = (obj.bbox.y1 + obj.bbox.y2) / 2.0
            for zone in self.zones:
                if zone.camera_id != obj.camera_id:
                    continue
                if zone.object_classes and obj.entity_class not in zone.object_classes:
                    continue
                if not zone.contains(center_x, center_y):
                    continue
                output.append(
                    Observation(
                        observation_id=(
                            f"zone:{obj.camera_id}:{obj.timestamp_ms}:"
                            f"{obj.entity_id}:{zone.name}"
                        ),
                        session_id=obj.session_id,
                        camera_id=obj.camera_id,
                        timestamp_ms=obj.timestamp_ms,
                        type=ObservationType.ZONE_RELATION,
                        entity_id=obj.entity_id,
                        entity_class=obj.entity_class,
                        confidence=obj.confidence,
                        relation=SpatialRelation.IN,
                        zone=zone.name,
                        model_name="zone-2d-baseline",
                        model_version="0.1",
                    )
                )
        return output
