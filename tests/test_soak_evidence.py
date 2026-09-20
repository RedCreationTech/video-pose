from video_pose.live_health import (
    EvidenceHealthSnapshot,
    LiveHealthSnapshot,
    RuntimeHealthSnapshot,
)
from video_pose.soak import SoakMonitor, SoakThresholds


def _snapshot(
    *,
    evidence: EvidenceHealthSnapshot,
) -> LiveHealthSnapshot:
    return LiveHealthSnapshot(
        cameras=[],
        runtime=RuntimeHealthSnapshot(),
        evidence=evidence,
        ready=True,
    )


def test_soak_fails_on_evidence_health_gate() -> None:
    monitor = SoakMonitor(
        SoakThresholds(
            min_ready_ratio=1.0,
            max_evidence_drop_ratio=0.10,
            max_evidence_errors=0,
            fail_on_evidence_over_capacity=True,
        )
    )
    monitor.add(
        0,
        _snapshot(
            evidence=EvidenceHealthSnapshot(
                submitted_total=100,
                processed_total=70,
                dropped_total=30,
                errors_total=1,
                drop_ratio=0.30,
                over_capacity=True,
            )
        ),
    )
    report = monitor.report()
    assert report.passed is False
    assert report.evidence_drop_ratio == 0.30
    assert report.evidence_errors_total == 1
    assert report.evidence_over_capacity is True
    assert any("evidence_drop_ratio" in item for item in report.failures)
    assert any("evidence_errors_total" in item for item in report.failures)
    assert "evidence_over_capacity=true" in report.failures


def test_soak_ignores_evidence_gate_when_evidence_is_disabled() -> None:
    monitor = SoakMonitor(
        SoakThresholds(min_ready_ratio=1.0)
    )
    monitor.add(
        0,
        LiveHealthSnapshot(
            cameras=[],
            runtime=RuntimeHealthSnapshot(),
            evidence=None,
            ready=True,
        ),
    )
    report = monitor.report()
    assert report.passed is True
    assert report.evidence_drop_ratio is None
