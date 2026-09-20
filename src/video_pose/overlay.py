from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .observations import Observation, ObservationType


class PrimitiveType(StrEnum):
    BOX = "BOX"
    POINT = "POINT"
    TEXT = "TEXT"


@dataclass(frozen=True, slots=True)
class OverlayPrimitive:
    type: PrimitiveType
    camera_id: str
    label: str
    x1: float
    y1: float
    x2: float | None = None
    y2: float | None = None


def build_overlay_primitives(
    observations: list[Observation],
) -> list[OverlayPrimitive]:
    primitives: list[OverlayPrimitive] = []
    for observation in observations:
        if observation.bbox is not None:
            primitives.append(
                OverlayPrimitive(
                    type=PrimitiveType.BOX,
                    camera_id=observation.camera_id,
                    label=(
                        f"{observation.entity_class or observation.type.value} "
                        f"{observation.entity_id} "
                        f"{observation.confidence:.2f}"
                    ),
                    x1=observation.bbox.x1,
                    y1=observation.bbox.y1,
                    x2=observation.bbox.x2,
                    y2=observation.bbox.y2,
                )
            )
        if observation.point_2d is not None:
            primitives.append(
                OverlayPrimitive(
                    type=PrimitiveType.POINT,
                    camera_id=observation.camera_id,
                    label=(
                        f"{observation.entity_class or observation.type.value} "
                        f"{observation.confidence:.2f}"
                    ),
                    x1=observation.point_2d.x,
                    y1=observation.point_2d.y,
                )
            )
        if observation.type in {
            ObservationType.RELATION,
            ObservationType.ZONE_RELATION,
        }:
            label_parts = [
                observation.entity_id,
                observation.relation.value if observation.relation else "",
            ]
            if observation.target_id:
                label_parts.append(observation.target_id)
            if observation.zone:
                label_parts.append(observation.zone)
            primitives.append(
                OverlayPrimitive(
                    type=PrimitiveType.TEXT,
                    camera_id=observation.camera_id,
                    label=" ".join(part for part in label_parts if part),
                    x1=12,
                    y1=24,
                )
            )
    return primitives
