from pathlib import Path
from types import SimpleNamespace

from video_pose.live_health import LiveHealthRegistry
from video_pose.persistent_session_controller import (
    PersistentLiveSessionController,
)
from video_pose.realtime_rules import RealtimeRuleSession
from video_pose.rules import RuleEngine
from video_pose.runtime_config import load_analysis_config
from video_pose.session_controller import SessionStartRequest


class FakeHub:
    def __init__(self) -> None:
        self.start_calls = 0
        self.stop_calls = 0
        self.running = False
        self.manifest = SimpleNamespace(workstation_id="ws-persistent")
        self.health = LiveHealthRegistry(["front"])

    def start(self) -> None:
        self.start_calls += 1
        self.running = True

    def stop(self) -> None:
        self.stop_calls += 1
        self.running = False

    def health_snapshot(self):
        return self.health.snapshot()


class FakeSessionRuntime:
    def __init__(self, session_id: str) -> None:
        self.rule_session = RealtimeRuleSession(
            RuleEngine.from_yaml("fixtures/rules/pick-place.yaml"),
            session_id=session_id,
        )

    def start(self, _callback) -> None:
        pass

    def stop(self):
        return self.rule_session.finish(1000)


def runtime_factory(
    _config,
    *,
    hub,
    processing_queue_size: int,
    session_id: str,
):
    assert hub.running
    assert processing_queue_size == 2
    return FakeSessionRuntime(session_id)


def test_two_sessions_reuse_one_camera_hub(tmp_path: Path) -> None:
    hub = FakeHub()
    controller = PersistentLiveSessionController(
        load_analysis_config("configs/offline-demo.yaml"),
        hub=hub,  # type: ignore[arg-type]
        audit_root=tmp_path,
        runtime_factory=runtime_factory,
    )
    controller.start_hub()

    first = controller.start(
        SessionStartRequest(session_id="session-1")
    )
    controller.stop(first.session_id)

    second = controller.start(
        SessionStartRequest(session_id="session-2")
    )
    controller.stop(second.session_id)

    assert hub.start_calls == 1
    assert hub.stop_calls == 0
    controller.shutdown()
    assert hub.stop_calls == 1
