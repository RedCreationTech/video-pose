from __future__ import annotations

from dataclasses import dataclass, replace

from .observations import BoundingBox


@dataclass(frozen=True, slots=True)
class Detection:
    bbox: BoundingBox
    confidence: float
    class_name: str
    class_id: int | None = None
    source_id: str | None = None


@dataclass(frozen=True, slots=True)
class TrackedDetection:
    bbox: BoundingBox
    confidence: float
    class_name: str
    entity_id: str
    class_id: int | None = None
    source_id: str | None = None

    @classmethod
    def from_detection(cls, detection: Detection, entity_id: str) -> TrackedDetection:
        return cls(
            bbox=detection.bbox,
            confidence=detection.confidence,
            class_name=detection.class_name,
            entity_id=entity_id,
            class_id=detection.class_id,
            source_id=detection.source_id,
        )

    def with_entity_id(self, entity_id: str) -> TrackedDetection:
        return replace(self, entity_id=entity_id)
