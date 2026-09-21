from video_pose.runtime_config import load_analysis_config


def test_production_runtime_requires_model_warmup() -> None:
    loaded = load_analysis_config(
        "deploy/compose/runtime.example/runtime.yaml"
    )
    assert loaded.config.model_warmup.enabled is True
    assert loaded.config.readiness.require_model_warmup is True
