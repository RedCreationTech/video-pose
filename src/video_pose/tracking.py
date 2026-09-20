from __future__ import annotations

from dataclasses import dataclass

from .detections import Detection, TrackedDetection
from .observations import BoundingBox


def box_iou(left: BoundingBox, right: BoundingBox) -> float:
    x1 = max(left.x1, right.x1)
    y1 = max(left.y1, right.y1)
    x2 = min(left.x2, right.x2)
    y2 = min(left.y2, right.y2)
    width = max(0.0, x2 - x1)
    height = max(0.0, y2 - y1)
    intersection = width * height
    if intersection <= 0.0:
        return 0.0

    left_area = (left.x2 - left.x1) * (left.y2 - left.y1)
    right_area = (right.x2 - right.x1) * (right.y2 - right.y1)
    union = left_area + right_area - intersection
    return intersection / union if union > 0.0 else 0.0


@dataclass(slots=True)
class _Track:
    entity_id: str
    bbox: BoundingBox
    class_name: str
    missed: int = 0


class IoUTracker:
    """Small deterministic tracker for the single-operator MVP.

    It is deliberately model-independent. Production can replace it with
    ByteTrack/BoT-SORT while preserving TrackedDetection.
    """

    def __init__(
        self,
        *,
        prefix: str,
        iou_threshold: float = 0.35,
        max_missed: int = 8,
    ) -> None:
        self.prefix = prefix
        self.iou_threshold = iou_threshold
        self.max_missed = max_missed
        self._tracks: list[_Track] = []
        self._next_id = 1

    def update(self, detections: list[Detection]) -> list[TrackedDetection]:
        for track in self._tracks:
            track.missed += 1

        used_tracks: set[int] = set()
        output: list[TrackedDetection] = []
        for detection in detections:
            best_index: int | None = None
            best_iou = self.iou_threshold
            for index, track in enumerate(self._tracks):
                if index in used_tracks or track.class_name != detection.class_name:
                    continue
                value = box_iou(track.bbox, detection.bbox)
                if value >= best_iou:
                    best_iou = value
                    best_index = index

            if best_index is None:
                entity_id = f"{self.prefix}-{self._next_id:04d}"
                self._next_id += 1
                self._tracks.append(
                    _Track(
                        entity_id=entity_id,
                        bbox=detection.bbox,
                        class_name=detection.class_name,
                        missed=0,
                    )
                )
                used_tracks.add(len(self._tracks) - 1)
            else:
                track = self._tracks[best_index]
                track.bbox = detection.bbox
                track.missed = 0
                entity_id = track.entity_id
                used_tracks.add(best_index)

            output.append(TrackedDetection.from_detection(detection, entity_id))

        self._tracks = [
            track for track in self._tracks if track.missed <= self.max_missed
        ]
        return output
