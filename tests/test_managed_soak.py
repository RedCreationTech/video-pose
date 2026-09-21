from video_pose.live_health import (
    EvidenceHealthSnapshot,
    LiveHealthSnapshot,
    RuntimeHealthSnapshot,
)
from video_pose.managed_soak import (
    ManagedSoakMonitor,
    ManagedSoakThresholds,
)
from video_pose.soak import SoakThresholds


def _health() -> LiveHealthSnapshot:
    return LiveHealthSnapshot(
        cameras=[],
        runtime=RuntimeHealthSnapshot(),
        evidence=EvidenceHealthSnapshot(
            submitted_total=10,
            processed_total=10,
            drop_ratio=0.0,
        ),
        ready=True,
    )


def test_managed_soak_passes_repeated_session_lifecycle() -> None:
    monitor = ManagedSoakMonitor(
        health_thresholds=SoakThresholds(min_ready_ratio=1.0),
        managed_thresholds=ManagedSoakThresholds(
            min_completed_sessions=2,
        ),
    )
    monitor.record_hub_start(success=True)
    monitor.record_model_pool_loaded(True)
    monitor.record_session_start(100, success=True)
    monitor.record_session_stop(150, success=True)
    monitor.record_session_start(120, success=True)
    monitor.record_session_stop(140, success=True)
    monitor.add_health(0, _health())
    monitor.add_health(60, _health())

    report = monitor.report()
    assert report.passed is True
    assert report.sessions_started == 2
    assert report.sessions_completed == 2


def test_managed_soak_fails_session_transition_gate() -> None:
    monitor = ManagedSoakMonitor(
        health_thresholds=SoakThresholds(min_ready_ratio=1.0),
        managed_thresholds=ManagedSoakThresholds(
            max_session_start_errors=0,
            max_session_stop_errors=0,
            max_session_start_latency_ms=500,
            max_session_stop_latency_ms=500,
            min_completed_sessions=1,
        ),
    )
    monitor.record_hub_start(success=True)
    monitor.record_model_pool_loaded(True)
    monitor.record_session_start(800, success=False)
    monitor.record_session_stop(900, success=False)
    monitor.add_health(0, _health())

    report = monitor.report()
    assert report.passed is False
    assert any("session_start_errors_total" in item for item in report.failures)
    assert any("session_stop_errors_total" in item for item in report.failures)
    assert any("max_session_start_latency_ms" in item for item in report.failures)
    assert any("max_session_stop_latency_ms" in item for item in report.failures)
    assert any("sessions_completed" in item for item in report.failures)


def test_managed_soak_fails_when_model_pool_is_not_loaded() -> None:
    monitor = ManagedSoakMonitor(
        health_thresholds=SoakThresholds(min_ready_ratio=1.0),
    )
    monitor.record_hub_start(success=True)
    monitor.record_model_pool_loaded(False)
    monitor.record_session_start(10, success=True)
    monitor.record_session_stop(10, success=True)
    monitor.add_health(0, _health())

    report = monitor.report()
    assert report.passed is False
    assert "model_pool_loaded=false" in report.failures
