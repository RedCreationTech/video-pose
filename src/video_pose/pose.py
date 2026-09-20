from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from .detections import TrackedDetection

COCO_KEYPOINT_NAMES = (
    "nose",
    "left_eye",
    "right_eye",
    "left_ear",
    "right_ear",
    "left_shoulder",
    "right_shoulder",
    "left_elbow",
    "right_elbow",
    "left_wrist",
    "right_wrist",
    "left_hip",
    "right_hip",
    "left_knee",
    "right_knee",
    "left_ankle",
    "right_ankle",
)


@dataclass(frozen=True, slots=True)
class PoseKeypoint:
    name: str
    x: float
    y: float
    confidence: float


@dataclass(frozen=True, slots=True)
class PoseEstimate:
    person_entity_id: str
    keypoints: tuple[PoseKeypoint, ...]


class PoseEstimator(Protocol):
    def infer(
        self,
        image: Any,
        persons: list[TrackedDetection],
    ) -> list[PoseEstimate]: ...
