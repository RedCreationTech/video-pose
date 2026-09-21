from video_pose.runtime_config import load_analysis_config


def test_production_runtime_template_enables_start_gate() -> None:
    loaded = load_analysis_config(
        "deploy/compose/runtime.example/runtime.yaml"
    )
    readiness = loaded.config.readiness
    assert readiness.enabled is True
    assert readiness.require_sync is True
    assert readiness.require_persistence is True
    assert readiness.block_persistence_degraded is True
