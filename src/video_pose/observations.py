from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ObservationType(StrEnum):
    PERSON = "PERSON"
    OBJECT = "OBJECT"
    BODY_KEYPOINT = "BODY_KEYPOINT"
    HAND_KEYPOINT = "HAND_KEYPOINT"
    RELATION = "RELATION"
    ZONE_RELATION = "ZONE_RELATION"


class SpatialRelation(StrEnum):
    IN = "IN"
    OUTSIDE = "OUTSIDE"
    NEAR = "NEAR"
    TOUCHING = "TOUCHING"
    HELD_BY = "HELD_BY"
    FREE = "FREE"


class Point2D(BaseModel):
    x: float
    y: float


class Point3D(BaseModel):
    x: float
    y: float
    z: float


class BoundingBox(BaseModel):
    x1: float
    y1: float
    x2: float
    y2: float

    @model_validator(mode="after")
    def valid_bounds(self) -> BoundingBox:
        if self.x2 <= self.x1 or self.y2 <= self.y1:
            raise ValueError("bounding box must have positive width and height")
        return self


class Observation(BaseModel):
    """Normalized perception fact independent from any specific AI model."""

    model_config = ConfigDict(extra="allow")

    observation_id: str
    session_id: str
    camera_id: str
    timestamp_ms: float = Field(ge=0.0)
    type: ObservationType
    entity_id: str
    entity_class: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    bbox: BoundingBox | None = None
    point_2d: Point2D | None = None
    point_3d: Point3D | None = None
    relation: SpatialRelation | None = None
    target_id: str | None = None
    zone: str | None = None
    model_name: str = "fixture"
    model_version: str = "0"
    attributes: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def relation_fields_are_consistent(self) -> Observation:
        if self.type == ObservationType.RELATION and self.relation is None:
            raise ValueError("RELATION observation requires relation")
        if self.type == ObservationType.ZONE_RELATION:
            if self.relation not in {SpatialRelation.IN, SpatialRelation.OUTSIDE}:
                raise ValueError("ZONE_RELATION requires IN or OUTSIDE relation")
            if not self.zone:
                raise ValueError("ZONE_RELATION requires zone")
        if self.relation == SpatialRelation.HELD_BY and not self.target_id:
            raise ValueError("HELD_BY relation requires target_id")
        return self
