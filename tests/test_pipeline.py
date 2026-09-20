from video_pose.baseline_action import PickPlaceActionRecognizer
from video_pose.observations import Observation
from video_pose.pipeline import VideoPosePipeline
from video_pose.video_manifest import CameraPosition
from video_pose.video_replay import FrameRef, SynchronizedFrameSet


def _frame_set(timestamp_ms: float) -> SynchronizedFrameSet:
    frames = {
        position: FrameRef(
            camera_id=f"cam-{position.value.lower()}",
            position=position,
            uri=f"{position.value.lower()}.mp4",
            source_timestamp_ms=timestamp_ms,
            normalized_timestamp_ms=timestamp_ms,
        )
        for position in CameraPosition
    }
    return SynchronizedFrameSet(
        reference_timestamp_ms=timestamp_ms,
        frames=frames,
        skew_ms=0.0,
    )


class FixturePerception:
    def infer(self, frame_set: SynchronizedFrameSet) -> list[Observation]:
        timestamp = frame_set.reference_timestamp_ms
        if timestamp == 0.0:
            return [
                Observation.model_validate(
                    {
                        "observation_id": "free-0",
                        "session_id": "pipeline-demo",
                        "camera_id": "cam-front",
                        "timestamp_ms": 0,
                        "type": "RELATION",
                        "entity_id": "part-1",
                        "entity_class": "component_A",
                        "confidence": 0.95,
                        "relation": "FREE",
                    }
                ),
                Observation.model_validate(
                    {
                        "observation_id": "zone-0",
                        "session_id": "pipeline-demo",
                        "camera_id": "cam-left",
                        "timestamp_ms": 0,
                        "type": "ZONE_RELATION",
                        "entity_id": "part-1",
                        "entity_class": "component_A",
                        "confidence": 0.94,
                        "relation": "IN",
                        "zone": "component_bin_A",
                    }
                ),
            ]
        if timestamp == 1000.0:
            return [
                Observation.model_validate(
                    {
                        "observation_id": "held-1",
                        "session_id": "pipeline-demo",
                        "camera_id": "cam-left",
                        "timestamp_ms": 1000,
                        "type": "RELATION",
                        "entity_id": "part-1",
                        "entity_class": "component_A",
                        "confidence": 0.96,
                        "relation": "HELD_BY",
                        "target_id": "right_hand",
                    }
                )
            ]
        return []


def test_pipeline_keeps_model_boundary_outside_action_logic() -> None:
    pipeline = VideoPosePipeline(
        perception=FixturePerception(),
        action_recognizer=PickPlaceActionRecognizer("pipeline-demo"),
    )
    actions = pipeline.process([_frame_set(0.0), _frame_set(1000.0)])
    assert len(actions) == 1
    assert actions[0].action.value == "PICK"
    assert actions[0].source_zone == "component_bin_A"
