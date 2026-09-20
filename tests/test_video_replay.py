from pathlib import Path

from video_pose.video_manifest import CameraPosition
from video_pose.video_replay import ReplayPlanner

ROOT = Path(__file__).resolve().parents[1]


class FakeTimestampProvider:
    def timestamps_ms(self, uri: str) -> list[float]:
        name = Path(uri).name
        values = {
            "front.mp4": [0.0, 40.0, 80.0],
            "rear.mp4": [-3.2, 36.8, 76.8],
            "left.mp4": [2.1, 42.1, 82.1],
            "right.mp4": [-1.6, 38.4, 78.4],
        }
        return values[name]


def test_replay_planner_applies_clock_offsets_and_builds_four_views() -> None:
    planner = ReplayPlanner.from_manifest_file(
        ROOT / "fixtures/replay/session-manifest.yaml",
        timestamp_provider=FakeTimestampProvider(),
    )
    frame_sets = planner.plan()
    assert len(frame_sets) == 3
    assert all(len(frame_set.frames) == 4 for frame_set in frame_sets)
    assert max(frame_set.skew_ms for frame_set in frame_sets) < 0.001
    first = frame_sets[0]
    assert first.frames[CameraPosition.REAR].source_timestamp_ms == -3.2
    assert first.frames[CameraPosition.REAR].normalized_timestamp_ms == 0.0
