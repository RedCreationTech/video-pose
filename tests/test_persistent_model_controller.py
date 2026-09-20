from pathlib import Path
from types import SimpleNamespace

from video_pose.live_health import LiveHealthRegistry
from video_pose.model_pool import PersistentModelPool
from video_pose.persistent_session_controller import (
    PersistentLiveSessionController,
)
from video_pose.realtime_rules import RealtimeRuleSession
from video_pose.rules import RuleEngine
from video_pose.runtime_config import load_analysis_config
from video_pose.session_controller import SessionStartRequest


class FakeHeavyModel:
    def __init__(self) -> None:
        self.load_calls = 0

    def load(self) -> None:
        self.load_calls += 1


class FakeHub:
    def __init__(self) -> None:
        self.running = False
        self.start_calls = 0
        self.stop_calls = 0
        self.manifest = SimpleNamespace(workstation_id="ws-model")
        self.health = LiveHealthRegistry(["front"])

    def start(self) -> None:
        self.start_calls += 1
        self.running = True

    def stop(self) -> None:
        self.stop_calls += 1
        self.running = False

    def health_snapshot(self):
        return self.health.snapshot()


class FakeRuntime:
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
    model_pool,
    processing_queue_size: int,
    session_id: str,
):
    assert hub.running
    assert model_pool.loaded
    assert processing_queue_size == 2
    return FakeRuntime(session_id)


def test_model_pool_survives_multiple_sessions(tmp_path: Path) -> None:
    detector = FakeHeavyModel()
    pool = PersistentModelPool(
        detector=detector,
        pose_estimator=None,
    )
    hub = FakeHub()
    controller = PersistentLiveSessionController(
        load_analysis_config("configs/offline-demo.yaml"),
        hub=hub,  # type: ignore[arg-type]
        model_pool=pool,
        audit_root=tmp_path,
        runtime_factory=runtime_factory,
    )

    controller.start_hub()
    first = controller.start(SessionStartRequest(session_id="m1"))
    controller.stop(first.session_id)
    second = controller.start(SessionStartRequest(session_id="m2"))
    controller.stop(second.session_id)
    controller.shutdown()

    assert detector.load_calls == 1
    assert hub.start_calls == 1
    assert hub.stop_calls == 1
