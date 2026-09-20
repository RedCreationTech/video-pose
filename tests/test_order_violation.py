from pathlib import Path

from video_pose.replay import run_replay

ROOT = Path(__file__).resolve().parents[1]


def test_out_of_order_event_is_explicit_but_step_can_recover() -> None:
    result = run_replay(
        ROOT / "fixtures/replay/assembly-tool-wrong-order.jsonl",
        ROOT / "fixtures/rules/assembly-tool.yaml",
    )
    assert result.passed is False
    order = [item for item in result.violations if item.type == "ORDER"]
    assert len(order) == 1
    assert order[0].step == "S020"
    assert order[0].event_id == "early-place"
    assert result.score == 90.0
    assert all(step.state.value == "COMPLETED" for step in result.steps)
