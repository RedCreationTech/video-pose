from pathlib import Path

from video_pose.replay import run_replay

ROOT = Path(__file__).resolve().parents[1]
RULES = ROOT / "fixtures/rules/start-delay-demo.yaml"


def test_late_step_completes_but_records_timeout() -> None:
    result = run_replay(
        ROOT / "fixtures/replay/start-delay-late.jsonl",
        RULES,
    )
    timeout = [item for item in result.violations if item.type == "TIMEOUT"]
    assert len(timeout) == 1
    assert timeout[0].event_id == "place"
    assert result.steps[1].state.value == "COMPLETED"
    assert result.passed is False


def test_step_started_too_soon_records_minor_temporal_violation() -> None:
    result = run_replay(
        ROOT / "fixtures/replay/start-delay-fast.jsonl",
        RULES,
    )
    temporal = [
        item
        for item in result.violations
        if item.type == "TEMPORAL"
    ]
    assert len(temporal) == 1
    assert temporal[0].actual["reason"] == "started_too_soon"
    assert result.score == 98.0
    assert result.passed is True


def test_ready_step_times_out_at_session_end_without_missing_duplicate() -> None:
    result = run_replay(
        ROOT / "fixtures/replay/start-delay-missing.jsonl",
        RULES,
        session_end_ms=2301,
    )
    types = [item.type for item in result.violations]
    assert types == ["TIMEOUT"]
    assert result.steps[1].state.value == "VIOLATED"
    assert result.passed is False
