from pathlib import Path

from video_pose.fault_scenario import run_fault_scenario


ROOT = Path(__file__).resolve().parents[1]


def test_camera_outage_fault_scenario_rearms_after_recovery() -> None:
    result = run_fault_scenario(
        ROOT / "fixtures/faults/camera-outage.yaml"
    )
    assert result.matched_expectations is True
    assert len(result.violations) == 2
    assert result.violations[0].event_id != result.violations[1].event_id


def test_sync_stall_fault_scenario_fails_session() -> None:
    result = run_fault_scenario(
        ROOT / "fixtures/faults/sync-stall.yaml"
    )
    assert result.matched_expectations is True
    assert result.final_session_passed is False


def test_sync_drift_fault_scenario_fails_session() -> None:
    result = run_fault_scenario(
        ROOT / "fixtures/faults/sync-drift.yaml"
    )
    assert result.matched_expectations is True
    assert result.violations[0].actual[
        "max_abs_drift_ms_per_minute"
    ] == 4.5
