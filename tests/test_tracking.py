from video_pose.detections import Detection
from video_pose.observations import BoundingBox
from video_pose.tracking import IoUTracker, box_iou


def _detection(x1: float, x2: float) -> Detection:
    return Detection(
        bbox=BoundingBox(x1=x1, y1=0, x2=x2, y2=100),
        confidence=0.9,
        class_name="person",
    )


def test_box_iou() -> None:
    left = BoundingBox(x1=0, y1=0, x2=100, y2=100)
    right = BoundingBox(x1=50, y1=0, x2=150, y2=100)
    assert round(box_iou(left, right), 3) == 0.333


def test_iou_tracker_keeps_operator_identity() -> None:
    tracker = IoUTracker(prefix="front-person", iou_threshold=0.3)
    first = tracker.update([_detection(0, 100)])
    second = tracker.update([_detection(10, 110)])
    assert first[0].entity_id == second[0].entity_id


def test_iou_tracker_creates_new_identity_for_far_detection() -> None:
    tracker = IoUTracker(prefix="front-person", iou_threshold=0.3)
    first = tracker.update([_detection(0, 100)])
    second = tracker.update([_detection(300, 400)])
    assert first[0].entity_id != second[0].entity_id
