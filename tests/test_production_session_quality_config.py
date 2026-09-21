from video_pose.runtime_config import load_analysis_config


def test_production_runtime_enables_session_quality_guard() -> None:
    loaded = load_analysis_config(
        "deploy/compose/runtime.example/runtime.yaml"
    )
    quality = loaded.config.session_quality
    assert quality.enabled is True
    assert quality.monitor_cameras is True
    assert quality.monitor_sync is True
    assert quality.severity == "CRITICAL"
