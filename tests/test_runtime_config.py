from pathlib import Path

from video_pose.runtime_config import load_analysis_config

ROOT = Path(__file__).resolve().parents[1]


def test_offline_config_loads_and_resolves_paths() -> None:
    loaded = load_analysis_config(ROOT / "configs/offline-demo.yaml")
    assert loaded.config.detector.confidence == 0.4
    assert loaded.config.relation.hold_frames == 2
    assert loaded.config.actions.tool_classes == {"torque_wrench"}
    assert loaded.config.triangulation.enabled is False
    manifest = loaded.resolve(loaded.config.manifest)
    assert manifest == (ROOT / "fixtures/replay/session-manifest.yaml").resolve()
