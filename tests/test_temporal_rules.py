from pathlib import Path

from video_pose.replay import run_replay

ROOT = Path(__file__).resolve().parents[1]
RULES = ROOT / "fixtures/rules/timing-demo.yaml"


def test_temporal_rule_accepts_duration_in_range() -> None:
    result = run_replay(
        ROOT / "fixtures/replay/timing-compliant.jsonl",
        RULES,
    )
    assert result.passed is True
    assert result.score == 100.0
    assert result.violations == []


def test_temporal_rule_records_minor_violation_but_completes_step() -> None:
    result = run_replay(
        ROOT / "fixtures/replay/timing-too-fast.jsonl",
        RULES,
    )
    assert result.passed is True
    assert result.score == 98.0
    assert result.steps[0].state.value == "COMPLETED"
    temporal = [item for item in result.violations if item.type == "TEMPORAL"]
    assert len(temporal) == 1
    assert temporal[0].actual["reason"] == "too_short"
