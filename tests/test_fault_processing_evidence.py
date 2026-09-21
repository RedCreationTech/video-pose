from pathlib import Path

from video_pose.fault_scenario import run_fault_scenario

ROOT = Path(__file__).resolve().parents[1]


def test_processing_error_fault_scenario() -> None:
    result = run_fault_scenario(
        ROOT / "fixtures/faults/processing-error.yaml"
    )
    assert result.matched_expectations is True
    assert result.violations[0].rule_id == "SYSTEM-QUALITY-PROCESSING"


def test_processing_drop_fault_scenario() -> None:
    result = run_fault_scenario(
        ROOT / "fixtures/faults/processing-drop.yaml"
    )
    assert result.matched_expectations is True
    assert result.violations[0].actual["drop_ratio"] > 0.20


def test_evidence_pressure_fault_scenario() -> None:
    result = run_fault_scenario(
        ROOT / "fixtures/faults/evidence-pressure.yaml"
    )
    assert result.matched_expectations is True
    assert result.violations[0].actual["over_capacity"] is True
