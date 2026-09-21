from video_pose.runtime_config import load_analysis_config


def test_production_runtime_monitors_processing_and_evidence_quality() -> None:
    loaded = load_analysis_config(
        "deploy/compose/runtime.example/runtime.yaml"
    )
    quality = loaded.config.session_quality
    assert quality.monitor_processing is True
    assert quality.max_processing_error_delta == 0
    assert quality.monitor_evidence is True
    assert quality.max_evidence_error_delta == 0
    assert quality.block_evidence_over_capacity is True
