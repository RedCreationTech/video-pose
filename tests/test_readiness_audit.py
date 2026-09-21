from pathlib import Path
from types import SimpleNamespace

from video_pose.live_health import LiveHealthSnapshot, RuntimeHealthSnapshot
from video_pose.runtime_config import load_analysis_config
from video_pose.session_audit import SessionAuditWriter
from video_pose.session_readiness import evaluate_session_readiness


class FakeHub:
    running = True
    manifest = SimpleNamespace(cameras=[])

    def health_snapshot(self):
        return LiveHealthSnapshot(
            cameras=[],
            runtime=RuntimeHealthSnapshot(),
            ready=True,
        )


class FakePool:
    loaded = True


def test_readiness_blocks_degraded_audit(
    tmp_path: Path,
) -> None:
    loaded = load_analysis_config("configs/offline-demo.yaml")
    loaded.config.readiness.enabled = True
    loaded.config.readiness.require_all_cameras_online = False
    loaded.config.readiness.require_sync = False
    loaded.config.readiness.require_storage_headroom = False
    loaded.config.readiness.block_audit_degraded = True

    blocker = tmp_path / "blocker"
    blocker.write_text("x", encoding="utf-8")
    writer = SessionAuditWriter(blocker / "audit")
    try:
        writer.probe()
    except Exception:
        pass

    report = evaluate_session_readiness(
        loaded,
        hub=FakeHub(),
        model_pool=FakePool(),
        repository=None,
        audit_root=tmp_path,
        audit_writer=writer,
    )
    check = next(
        item
        for item in report.checks
        if item.name == "audit-health"
    )
    assert check.passed is False
    assert report.ready is False
