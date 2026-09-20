from pathlib import Path

import pytest
from pydantic import ValidationError

from video_pose.video_manifest import ReplayManifest, load_manifest

ROOT = Path(__file__).resolve().parents[1]


def test_four_view_manifest_is_valid() -> None:
    manifest = load_manifest(ROOT / "fixtures/replay/session-manifest.yaml")
    assert manifest.session_id == "demo-four-view"
    assert len(manifest.cameras) == 4


def test_manifest_requires_all_four_positions() -> None:
    with pytest.raises(ValidationError):
        ReplayManifest.model_validate(
            {
                "session_id": "s1",
                "workstation_id": "ws1",
                "cameras": [
                    {"camera_id": "front", "position": "FRONT", "uri": "front.mp4"},
                    {"camera_id": "left", "position": "LEFT", "uri": "left.mp4"},
                ],
            }
        )
