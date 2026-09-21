from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_edge_compose_exposes_release_identity_environment() -> None:
    payload = yaml.safe_load(
        (
            ROOT / "deploy/compose/docker-compose.yml"
        ).read_text(encoding="utf-8")
    )
    environment = payload["services"]["edge"]["environment"]
    assert "VIDEO_POSE_GIT_SHA" in environment
    assert "VIDEO_POSE_IMAGE_DIGEST" in environment
