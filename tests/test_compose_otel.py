from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_edge_compose_exposes_optional_otel_environment() -> None:
    payload = yaml.safe_load(
        (
            ROOT / "deploy/compose/docker-compose.yml"
        ).read_text(encoding="utf-8")
    )
    environment = payload["services"]["edge"]["environment"]
    assert "VIDEO_POSE_OTEL_ENABLED" in environment
    assert "OTEL_SERVICE_NAME" in environment
    assert "OTEL_EXPORTER_OTLP_ENDPOINT" in environment
