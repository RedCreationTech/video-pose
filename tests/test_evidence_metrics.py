from video_pose.live_health import (
    EvidenceHealthSnapshot,
    LiveHealthSnapshot,
    RuntimeHealthSnapshot,
)
from video_pose.live_metrics import render_prometheus


def test_prometheus_renders_evidence_metrics() -> None:
    snapshot = LiveHealthSnapshot(
        cameras=[],
        runtime=RuntimeHealthSnapshot(),
        evidence=EvidenceHealthSnapshot(
            submitted_total=100,
            processed_total=90,
            dropped_total=10,
            errors_total=2,
            queue_depth=1,
            queue_capacity=2,
            drop_ratio=0.1,
            artifact_count=12,
            protected_count=3,
            total_bytes=2048,
            max_total_bytes=4096,
            over_capacity=False,
        ),
        ready=True,
    )
    rendered = render_prometheus(snapshot)
    assert "video_pose_evidence_dropped_total 10" in rendered
    assert "video_pose_evidence_drop_ratio 0.1" in rendered
    assert "video_pose_evidence_protected_artifacts 3" in rendered
    assert "video_pose_evidence_storage_bytes 2048" in rendered
    assert "video_pose_evidence_over_capacity 0" in rendered
