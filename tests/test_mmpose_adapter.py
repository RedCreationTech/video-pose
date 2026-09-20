from types import SimpleNamespace

from video_pose.adapters.mmpose_topdown import MMPoseTopDownEstimator
from video_pose.detections import TrackedDetection
from video_pose.observations import BoundingBox


class FakeArray:
    def __init__(self, value: list[object]) -> None:
        self.value = value

    def tolist(self) -> list[object]:
        return self.value


def fake_inference(
    _model: object,
    _image: object,
    *,
    bboxes: list[list[float]],
    bbox_format: str,
) -> list[SimpleNamespace]:
    assert bbox_format == "xyxy"
    assert len(bboxes) == 1
    pred_instances = SimpleNamespace(
        keypoints=FakeArray([[[20.0, 30.0], [40.0, 50.0]]]),
        keypoint_scores=FakeArray([[0.9, 0.8]]),
    )
    return [SimpleNamespace(pred_instances=pred_instances)]


def test_mmpose_adapter_maps_pose_to_tracked_person() -> None:
    estimator = MMPoseTopDownEstimator(
        "config.py",
        "checkpoint.pth",
        model=object(),
        inference_fn=fake_inference,
        keypoint_names=("nose", "left_eye"),
    )
    person = TrackedDetection(
        bbox=BoundingBox(x1=0, y1=0, x2=100, y2=200),
        confidence=0.95,
        class_name="person",
        entity_id="front-person-0001",
    )
    output = estimator.infer("image", [person])
    assert output[0].person_entity_id == "front-person-0001"
    assert output[0].keypoints[0].name == "nose"
    assert output[0].keypoints[1].confidence == 0.8
