from pathlib import Path

from video_pose.storage_health import sample_storage


def test_storage_health_uses_nearest_existing_parent(
    tmp_path: Path,
) -> None:
    target = tmp_path / "future" / "audit"
    snapshot = sample_storage("audit", target)
    assert snapshot.name == "audit"
    assert snapshot.configured_path.endswith("future/audit")
    assert snapshot.probe_path == str(tmp_path)
    assert snapshot.total_bytes > 0
    assert snapshot.free_bytes >= 0
    assert 0.0 <= snapshot.free_ratio <= 1.0
