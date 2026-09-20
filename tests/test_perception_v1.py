from video_pose.detections import Detection
from video_pose.frames import DecodedFrame
from video_pose.observations import BoundingBox, ObservationType
from video_pose.perception_v1 import PerceptionV1Model
from video_pose.pose import PoseEstimate, PoseKeypoint
from video_pose.video_manifest import CameraPosition
from video_pose.video_replay import FrameRef


class FakeDetector:
    model_name = "fake-detector"
    model_version = "1"

    def detect(self, _image: object) -> list[Detection]:
        return [
            Detection(
                bbox=BoundingBox(x1=0, y1=0, x2=100, y2=200),
                confidence=0.95,
                class_name="person",
            ),
            Detection(
                bbox=BoundingBox(x1=120, y1=20, x2=180, y2=80),
                confidence=0.91,
                class_name="torque_wrench",
            ),
        ]


class FakePose:
    def infer(self, _image: object, persons: list[object]) -> list[PoseEstimate]:
        person = persons[0]
        return [
            PoseEstimate(
                person_entity_id=person.entity_id,
                keypoints=(
                    PoseKeypoint(
                        name="right_wrist",
                        x=50.0,
                        y=100.0,
                        confidence=0.88,
                    ),
                ),
            )
        ]


def test_perception_v1_outputs_person_object_and_pose() -> None:
    model = PerceptionV1Model(FakeDetector(), FakePose())
    frame = DecodedFrame(
        ref=FrameRef(
            camera_id="cam-front",
            position=CameraPosition.FRONT,
            uri="front.mp4",
            source_timestamp_ms=1000,
            normalized_timestamp_ms=1000,
        ),
        image="pixels",
    )
    output = model.infer(frame, session_id="session-1")
    kinds = {item.type for item in output}
    assert ObservationType.PERSON in kinds
    assert ObservationType.OBJECT in kinds
    assert ObservationType.BODY_KEYPOINT in kinds
    person = next(item for item in output if item.type == ObservationType.PERSON)
    wrist = next(
        item for item in output if item.type == ObservationType.BODY_KEYPOINT
    )
    assert wrist.attributes["person_id"] == person.entity_id
