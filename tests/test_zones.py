from pathlib import Path

from video_pose.observations import Observation
from video_pose.zones import ZoneRelationBuilder, load_zones

ROOT = Path(__file__).resolve().parents[1]


def test_zone_builder_maps_object_center() -> None:
    config = load_zones(ROOT / "fixtures/zones/pick-place-front.yaml")
    builder = ZoneRelationBuilder(config.zones)
    obj = Observation.model_validate(
        {
            "observation_id": "part",
            "session_id": "s1",
            "camera_id": "cam-front",
            "timestamp_ms": 0,
            "type": "OBJECT",
            "entity_id": "part-1",
            "entity_class": "component_A",
            "confidence": 0.95,
            "bbox": {"x1": 50, "y1": 50, "x2": 100, "y2": 100},
        }
    )
    output = builder.enrich([obj])
    assert len(output) == 1
    assert output[0].zone == "component_bin_A"
