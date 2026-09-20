from pathlib import Path

from video_pose.replay import run_replay

ROOT = Path(__file__).resolve().parents[1]


def test_extended_industrial_sop_passes() -> None:
    result = run_replay(
        ROOT / "fixtures/replay/assembly-tool-compliant.jsonl",
        ROOT / "fixtures/rules/assembly-tool.yaml",
    )
    assert result.passed is True
    assert result.score == 100.0
    assert [step.state.value for step in result.steps] == [
        "COMPLETED",
        "COMPLETED",
        "COMPLETED",
        "COMPLETED",
        "COMPLETED",
    ]
