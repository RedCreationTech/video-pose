from pathlib import Path
from types import SimpleNamespace

from video_pose.live_health import LiveHealthRegistry
from video_pose.realtime_rules import RealtimeRuleSession
from video_pose.rules import RuleEngine
from video_pose.runtime_config import load_analysis_config
from video_pose.session_controller import (
    LiveSessionController,
    SessionStartRequest,
)


class FakeRuntime:
    def __init__(self, session_id: str) -> None:
        self.rule_session = RealtimeRuleSession(
            RuleEngine.from_yaml("fixtures/rules/pick-place.yaml"),
            session_id=session_id,
        )
        self.gateway = SimpleNamespace(
            manifest=SimpleNamespace(workstation_id="ws-test")
        )
        self.health = LiveHealthRegistry(["front"])
        self.callback = None

    def start(self, callback):
        self.callback = callback

    def stop(self):
        return self.rule_session.finish(1000)

    def health_snapshot(self):
        return self.health.snapshot()


def fake_runtime_factory(
    _config,
    *,
    processing_queue_size: int,
    session_id: str,
):
    assert processing_queue_size == 2
    return FakeRuntime(session_id)


def test_controller_owns_session_and_audit(tmp_path: Path) -> None:
    controller = LiveSessionController(
        load_analysis_config("configs/offline-demo.yaml"),
        audit_root=tmp_path,
        runtime_factory=fake_runtime_factory,
    )
    state = controller.start(
        SessionStartRequest(
            session_id="managed-1",
            operator_id="op-1",
        )
    )
    assert state.status == "RUNNING"
    assert state.session_id == "managed-1"
    assert controller.current() is not None

    final = controller.stop("managed-1")
    assert final.result.session_id == "managed-1"
    assert (tmp_path / "managed-1" / "final.json").exists()
    current = controller.current()
    assert current is not None
    assert current.status == "COMPLETED"
