from __future__ import annotations

from .detections import Detection, TrackedDetection
from .detector import ObjectDetector
from .frames import DecodedFrame
from .observations import Observation, ObservationType, Point2D
from .pose import PoseEstimator
from .tracking import IoUTracker


class PerceptionV1Model:
    """Detector + person/object tracking + optional top-down pose estimator."""

    def __init__(
        self,
        detector: ObjectDetector,
        pose_estimator: PoseEstimator | None = None,
        *,
        person_class: str = "person",
        person_confidence: float = 0.5,
        object_confidence: float = 0.4,
    ) -> None:
        self.detector = detector
        self.pose_estimator = pose_estimator
        self.person_class = person_class
        self.person_confidence = person_confidence
        self.object_confidence = object_confidence
        self._person_trackers: dict[str, IoUTracker] = {}
        self._object_trackers: dict[str, IoUTracker] = {}

    def infer(
        self,
        frame: DecodedFrame,
        *,
        session_id: str,
    ) -> list[Observation]:
        camera_id = frame.ref.camera_id
        detections = self.detector.detect(frame.image)
        persons = [
            detection
            for detection in detections
            if detection.class_name == self.person_class
            and detection.confidence >= self.person_confidence
        ]
        objects = [
            detection
            for detection in detections
            if detection.class_name != self.person_class
            and detection.confidence >= self.object_confidence
        ]

        person_tracker = self._person_trackers.setdefault(
            camera_id,
            IoUTracker(prefix=f"{camera_id}-person"),
        )
        object_tracker = self._object_trackers.setdefault(
            camera_id,
            IoUTracker(prefix=f"{camera_id}-object"),
        )
        tracked_persons = person_tracker.update(persons)
        tracked_objects = object_tracker.update(objects)

        observations: list[Observation] = []
        for person in tracked_persons:
            observations.append(
                self._detection_observation(
                    frame=frame,
                    session_id=session_id,
                    detection=person,
                    observation_type=ObservationType.PERSON,
                )
            )

        for tracked_object in tracked_objects:
            observations.append(
                self._detection_observation(
                    frame=frame,
                    session_id=session_id,
                    detection=tracked_object,
                    observation_type=ObservationType.OBJECT,
                )
            )

        if self.pose_estimator is not None and tracked_persons:
            for pose in self.pose_estimator.infer(frame.image, tracked_persons):
                for keypoint in pose.keypoints:
                    observations.append(
                        Observation(
                            observation_id=(
                                f"{camera_id}:{frame.ref.normalized_timestamp_ms}:"
                                f"{pose.person_entity_id}:{keypoint.name}"
                            ),
                            session_id=session_id,
                            camera_id=camera_id,
                            timestamp_ms=frame.ref.normalized_timestamp_ms,
                            type=ObservationType.BODY_KEYPOINT,
                            entity_id=f"{pose.person_entity_id}:{keypoint.name}",
                            entity_class=keypoint.name,
                            confidence=keypoint.confidence,
                            point_2d=Point2D(x=keypoint.x, y=keypoint.y),
                            model_name="pose-estimator",
                            model_version="v1",
                            attributes={"person_id": pose.person_entity_id},
                        )
                    )
        return observations

    def _detection_observation(
        self,
        *,
        frame: DecodedFrame,
        session_id: str,
        detection: TrackedDetection,
        observation_type: ObservationType,
    ) -> Observation:
        return Observation(
            observation_id=(
                f"{frame.ref.camera_id}:{frame.ref.normalized_timestamp_ms}:"
                f"{detection.entity_id}"
            ),
            session_id=session_id,
            camera_id=frame.ref.camera_id,
            timestamp_ms=frame.ref.normalized_timestamp_ms,
            type=observation_type,
            entity_id=detection.entity_id,
            entity_class=detection.class_name,
            confidence=detection.confidence,
            bbox=detection.bbox,
            model_name=self.detector.model_name,
            model_version=self.detector.model_version,
        )
