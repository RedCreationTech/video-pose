from pathlib import Path

import pytest

from video_pose.session_audit import SessionAuditWriter


def test_audit_writer_health_degrades_and_recovers(
    tmp_path: Path,
) -> None:
    blocker = tmp_path / "blocker"
    blocker.write_text("not a directory", encoding="utf-8")
    writer = SessionAuditWriter(blocker / "audit")

    with pytest.raises(OSError):
        writer.probe()
    degraded = writer.health()
    assert degraded.status == "DEGRADED"
    assert degraded.write_errors_total == 1
    assert degraded.last_error is not None

    blocker.unlink()
    blocker.mkdir()
    recovered = writer.probe()
    assert recovered.status == "READY"
    assert recovered.write_errors_total == 1
    assert recovered.last_error is None
