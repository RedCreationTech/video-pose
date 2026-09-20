from video_pose.fusion import fuse_observations
from video_pose.observations import Observation


def test_fusion_keeps_strongest_semantic_evidence() -> None:
    base = {
        "session_id": "s1",
        "timestamp_ms": 1000,
        "type": "RELATION",
        "entity_id": "part-1",
        "entity_class": "component_A",
        "relation": "HELD_BY",
        "target_id": "right_hand",
    }
    front = Observation.model_validate(
        {
            **base,
            "observation_id": "front-1",
            "camera_id": "front",
            "confidence": 0.82,
        }
    )
    left = Observation.model_validate(
        {
            **base,
            "observation_id": "left-1",
            "camera_id": "left",
            "confidence": 0.96,
        }
    )
    fused = fuse_observations([front, left])
    assert len(fused) == 1
    assert fused[0].observation_id == "left-1"
