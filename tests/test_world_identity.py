from video_pose.observations import Observation
from video_pose.world_identity import MultiViewIdentityProcessor


def _object(
    camera: str,
    entity_id: str,
    x: float,
    y: float,
) -> Observation:
    return Observation.model_validate(
        {
            "observation_id": f"{camera}-{entity_id}",
            "session_id": "s1",
            "camera_id": camera,
            "timestamp_ms": 1000,
            "type": "OBJECT",
            "entity_id": entity_id,
            "entity_class": "component_A",
            "confidence": 0.9,
            "point_3d": {"x": x, "y": y, "z": 0},
        }
    )


def test_multiview_objects_receive_same_world_identity() -> None:
    processor = MultiViewIdentityProcessor(distance_threshold=100)
    output = processor.process(
        [
            _object("cam-front", "front-part", 500, 300),
            _object("cam-left", "left-part", 530, 315),
        ]
    )
    assert output[0].entity_id == output[1].entity_id
    assert output[0].entity_id.startswith("world-component_A-")


def test_world_identity_persists_across_frames() -> None:
    processor = MultiViewIdentityProcessor(distance_threshold=100)
    first = processor.process([_object("cam-front", "front-a", 500, 300)])
    second = processor.process([_object("cam-front", "front-b", 540, 310)])
    assert first[0].entity_id == second[0].entity_id
