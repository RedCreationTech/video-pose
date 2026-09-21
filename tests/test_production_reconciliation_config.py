from video_pose.runtime_config import load_analysis_config


def test_production_runtime_requires_reconciled_persistence() -> None:
    loaded = load_analysis_config(
        "deploy/compose/runtime.example/runtime.yaml"
    )
    policy = loaded.config.readiness
    assert policy.require_persistence_reconciled is True
