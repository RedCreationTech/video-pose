from pathlib import Path

from video_pose.persistent_session_controller import (
    PersistentLiveSessionController,
)
from video_pose.runtime_config import load_analysis_config


def test_custom_runtime_factory_without_audit_keyword_remains_compatible(
    tmp_path: Path,
) -> None:
    controller = PersistentLiveSessionController(
        load_analysis_config("configs/offline-demo.yaml"),
        hub=object(),  # type: ignore[arg-type]
        audit_root=tmp_path,
        runtime_factory=lambda *_args, **_kwargs: None,
    )
    assert controller.audit.health().status == "READY"
