from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_edge_entrypoint_enables_reconcile_on_start() -> None:
    script = (
        ROOT / "deploy/edge/entrypoint.sh"
    ).read_text(encoding="utf-8")
    assert "VIDEO_POSE_DB_RECONCILE" in script
    assert "--reconcile-on-start" in script
