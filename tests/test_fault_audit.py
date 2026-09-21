from pathlib import Path

from video_pose.fault_scenario import run_fault_scenario

ROOT = Path(__file__).resolve().parents[1]


def test_audit_write_fault_scenario_fails_session() -> None:
    result = run_fault_scenario(
        ROOT / "fixtures/faults/audit-write-failure.yaml"
    )
    assert result.matched_expectations is True
    assert result.violations[0].rule_id == "SYSTEM-QUALITY-AUDIT"
