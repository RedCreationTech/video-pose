from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_edge_compose_enables_structured_json_logs() -> None:
    payload = yaml.safe_load(
        (
            ROOT / "deploy/compose/docker-compose.yml"
        ).read_text(encoding="utf-8")
    )
    environment = payload["services"]["edge"]["environment"]
    assert "VIDEO_POSE_LOG_FORMAT" in environment
    assert "VIDEO_POSE_LOG_LEVEL" in environment
