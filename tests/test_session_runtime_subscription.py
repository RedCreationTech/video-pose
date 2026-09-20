from video_pose.live_health import LiveHealthRegistry
from video_pose.session_runtime import SessionAnalysisRuntime


class FakeHub:
    def __init__(self) -> None:
        self.running = True
        self.health = LiveHealthRegistry([])
        self.subscribers = {}
        self.next_token = 0

    def subscribe(self, callback):
        self.next_token += 1
        token = str(self.next_token)
        self.subscribers[token] = callback
        return token

    def unsubscribe(self, token):
        self.subscribers.pop(token, None)

    def health_snapshot(self):
        return self.health.snapshot()


class FakePipeline:
    pass


class FakeRuleSession:
    def finish(self, _time):
        return "finished"


def test_session_runtime_subscribes_and_unsubscribes_without_stopping_hub() -> None:
    hub = FakeHub()
    runtime = SessionAnalysisRuntime(
        hub=hub,  # type: ignore[arg-type]
        pipeline=FakePipeline(),  # type: ignore[arg-type]
        rule_session=FakeRuleSession(),  # type: ignore[arg-type]
    )
    runtime.start(lambda _update: None)
    assert len(hub.subscribers) == 1
    result = runtime.stop()
    assert result == "finished"
    assert hub.running is True
    assert hub.subscribers == {}
