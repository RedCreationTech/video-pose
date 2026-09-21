from video_pose.live_health import (
    EvidenceHealthSnapshot,
    LiveHealthSnapshot,
    RuntimeHealthSnapshot,
)
from video_pose.runtime_config import SessionQualityRuntimeConfig
from video_pose.session_quality import SessionQualityMonitor


def test_processing_monitor_uses_session_local_counter_deltas() -> None:
    monitor = SessionQualityMonitor(
        SessionQualityRuntimeConfig(
            enabled=True,
            monitor_cameras=False,
            monitor_sync=False,
            monitor_processing=True,
            processing_grace_ms=500,
            max_processing_error_delta=0,
        ),
        camera_ids=[],
    )
    first = LiveHealthSnapshot(
        cameras=[],
        runtime=RuntimeHealthSnapshot(
            frame_sets_received_total=100,
            processing_errors_total=9,
        ),
        ready=True,
    )
    assert monitor.observe(first, now_monotonic_ms=0) == []

    failed = first.model_copy(
        update={
            "runtime": RuntimeHealthSnapshot(
                frame_sets_received_total=110,
                processing_errors_total=10,
            )
        }
    )
    assert monitor.observe(
        failed,
        now_monotonic_ms=100,
    ) == []
    incident = monitor.observe(
        failed,
        now_monotonic_ms=700,
    )
    assert len(incident) == 1
    assert incident[0].rule_id == "SYSTEM-QUALITY-PROCESSING"
    assert incident[0].actual["processing_errors_delta"] == 1


def test_evidence_monitor_uses_session_local_counter_deltas() -> None:
    monitor = SessionQualityMonitor(
        SessionQualityRuntimeConfig(
            enabled=True,
            monitor_cameras=False,
            monitor_sync=False,
            monitor_evidence=True,
            evidence_grace_ms=500,
            max_evidence_error_delta=0,
            max_evidence_drop_ratio=0.20,
        ),
        camera_ids=[],
    )
    baseline = LiveHealthSnapshot(
        cameras=[],
        runtime=RuntimeHealthSnapshot(),
        evidence=EvidenceHealthSnapshot(
            submitted_total=100,
            dropped_total=20,
            errors_total=5,
        ),
        ready=True,
    )
    assert monitor.observe(
        baseline,
        now_monotonic_ms=0,
    ) == []

    failed = baseline.model_copy(
        update={
            "evidence": EvidenceHealthSnapshot(
                submitted_total=110,
                dropped_total=25,
                errors_total=6,
                over_capacity=True,
            )
        }
    )
    assert monitor.observe(
        failed,
        now_monotonic_ms=100,
    ) == []
    incident = monitor.observe(
        failed,
        now_monotonic_ms=700,
    )
    assert len(incident) == 1
    assert incident[0].rule_id == "SYSTEM-QUALITY-EVIDENCE"
    assert incident[0].actual["errors_delta"] == 1
