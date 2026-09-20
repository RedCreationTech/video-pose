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
from video_pose.sql_repository import SQLAlchemySessionRepository


class FakeRuntime:
    def __init__(self, session_id: str) -> None:
        self.rule_session = RealtimeRuleSession(
            RuleEngine.from_yaml("fixtures/rules/pick-place.yaml"),
            session_id=session_id,
        )
        self.gateway = SimpleNamespace(
            manifest=SimpleNamespace(workstation_id="ws-db")
        )
        self.health = LiveHealthRegistry(["front"])

    def start(self, _callback):
        pass

    def stop(self):
        return self.rule_session.finish(1000)

    def health_snapshot(self):
        return self.health.snapshot()


def runtime_factory(
    _config,
    *,
    processing_queue_size: int,
    session_id: str,
):
    assert processing_queue_size == 2
    return FakeRuntime(session_id)


def test_controller_dual_writes_audit_and_repository(
    tmp_path: Path,
) -> None:
    repository = SQLAlchemySessionRepository(
        f"sqlite:///{tmp_path / 'sessions.db'}"
    )
    repository.create_schema()
    controller = LiveSessionController(
        load_analysis_config("configs/offline-demo.yaml"),
        audit_root=tmp_path / "audit",
        runtime_factory=runtime_factory,
        repository=repository,
    )
    state = controller.start(
        SessionStartRequest(
            session_id="dual-write",
            operator_id="operator-1",
        )
    )
    controller.stop(state.session_id)

    stored = repository.get_session("dual-write")
    assert stored is not None
    assert stored["session"]["status"] == "COMPLETED"
    assert (
        tmp_path
        / "audit"
        / "dual-write"
        / "final.json"
    ).exists()
