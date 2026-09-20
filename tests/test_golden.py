from pathlib import Path

from video_pose.golden import evaluate_golden_dataset

ROOT = Path(__file__).resolve().parents[1]


def test_golden_dataset_fixture_is_perfect() -> None:
    report = evaluate_golden_dataset(
        ROOT / "datasets/golden-v1/manifest.yaml"
    )
    assert report.session_count == 2
    assert report.session_pass_accuracy == 1.0
    assert report.actions.f1 == 1.0
    assert report.violations.f1 == 1.0
