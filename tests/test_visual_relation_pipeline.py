from pathlib import Path

from video_pose.baseline_action import PickPlaceActionRecognizer
from video_pose.observations import Observation
from video_pose.pipeline import VideoPosePipeline
from video_pose.relations import HumanObjectRelationBuilder
from video_pose.rules import RuleEngine
from video_pose.video_manifest import CameraPosition
from video_pose.video_replay import FrameRef, SynchronizedFrameSet
from video_pose.zones import Zone2D, ZoneRelationBuilder

ROOT = Path(__file__).resolve().parents[1]


def _frame_set(timestamp: float) -> SynchronizedFrameSet:
    ref = FrameRef(
        camera_id="cam-front",
        position=CameraPosition.FRONT,
        uri="front.mp4",
        source_timestamp_ms=timestamp,
        normalized_timestamp_ms=timestamp,
    )
    return SynchronizedFrameSet(
        reference_timestamp_ms=timestamp,
        frames={CameraPosition.FRONT: ref},
        skew_ms=0.0,
    )


class VisualFixturePerception:
    def infer(self, frame_set: SynchronizedFrameSet) -> list[Observation]:
        timestamp = frame_set.reference_timestamp_ms
        if timestamp < 100:
            box = {"x1": 50, "y1": 50, "x2": 100, "y2": 100}
            wrist = {"x": 400, "y": 400}
        elif timestamp < 300:
            box = {"x1": 50, "y1": 50, "x2": 100, "y2": 100}
            wrist = {"x": 75, "y": 75}
        else:
            box = {"x1": 550, "y1": 50, "x2": 600, "y2": 100}
            wrist = {"x": 400, "y": 400}

        return [
            Observation.model_validate(
                {
                    "observation_id": f"part-{timestamp}",
                    "session_id": "visual-demo",
                    "camera_id": "cam-front",
                    "timestamp_ms": timestamp,
                    "type": "OBJECT",
                    "entity_id": "part-1",
                    "entity_class": "component_A",
                    "confidence": 0.96,
                    "bbox": box,
                }
            ),
            Observation.model_validate(
                {
                    "observation_id": f"wrist-{timestamp}",
                    "session_id": "visual-demo",
                    "camera_id": "cam-front",
                    "timestamp_ms": timestamp,
                    "type": "BODY_KEYPOINT",
                    "entity_id": "person-1:right_wrist",
                    "entity_class": "right_wrist",
                    "confidence": 0.95,
                    "point_2d": wrist,
                    "attributes": {"person_id": "person-1"},
                }
            ),
        ]


def test_visual_relations_drive_pick_place_rules() -> None:
    zones = [
        Zone2D(
            name="component_bin_A",
            camera_id="cam-front",
            x1=0,
            y1=0,
            x2=200,
            y2=300,
            object_classes={"component_A"},
        ),
        Zone2D(
            name="assembly_zone",
            camera_id="cam-front",
            x1=500,
            y1=0,
            x2=800,
            y2=300,
            object_classes={"component_A"},
        ),
    ]
    pipeline = VideoPosePipeline(
        perception=VisualFixturePerception(),
        action_recognizer=PickPlaceActionRecognizer(
            "visual-demo",
            min_confidence=0.7,
        ),
        observation_enrichers=[
            ZoneRelationBuilder(zones),
            HumanObjectRelationBuilder(hold_frames=2, free_frames=1),
        ],
    )

    actions = pipeline.process(
        [
            _frame_set(0),
            _frame_set(120),
            _frame_set(160),
            _frame_set(320),
        ]
    )
    assert [action.action.value for action in actions] == ["PICK", "PLACE"]
    assert actions[0].source_zone == "component_bin_A"
    assert actions[1].target_zone == "assembly_zone"

    result = RuleEngine.from_yaml(
        ROOT / "fixtures/rules/pick-place.yaml"
    ).evaluate(actions)
    assert result.passed is True
    assert result.score == 100.0
