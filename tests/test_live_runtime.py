from video_pose.contracts import ActionEvent, ActionObject
from video_pose.live_runtime import LiveAnalysisRuntime
from video_pose.realtime_rules import RealtimeRuleSession
from video_pose.rules import RuleEngine
from video_pose.trace import FrameTrace
from video_pose.video_manifest import CameraPosition
from video_pose.video_replay import FrameRef, SynchronizedFrameSet


class FakeGateway:
    def start(self, _callback: object) -> None:
        pass

    def stop(self) -> None:
        pass


class FakePipeline:
    def process_with_trace(
        self,
        frame_sets: list[SynchronizedFrameSet],
    ) -> list[FrameTrace]:
        frame_set = frame_sets[0]
        action = ActionEvent(
            event_id="pick",
            session_id="live-test",
            sequence=1,
            action="PICK",
            object=ActionObject(id="part", **{"class": "component_A"}),
            source_zone="component_bin_A",
            started_at_ms=100,
            confidence=0.95,
        )
        return [
            FrameTrace(
                frame_set=frame_set,
                observations=(),
                actions=(action,),
            )
        ]


def _frame_set() -> SynchronizedFrameSet:
    ref = FrameRef(
        camera_id="front",
        position=CameraPosition.FRONT,
        uri="memory://front/1",
        source_timestamp_ms=100,
        normalized_timestamp_ms=100,
    )
    return SynchronizedFrameSet(
        reference_timestamp_ms=100,
        frames={CameraPosition.FRONT: ref},
        skew_ms=0,
    )


def test_live_runtime_drives_realtime_rule_session() -> None:
    engine = RuleEngine.from_yaml("fixtures/rules/pick-place.yaml")
    runtime = LiveAnalysisRuntime(
        gateway=FakeGateway(),  # type: ignore[arg-type]
        pipeline=FakePipeline(),  # type: ignore[arg-type]
        rule_session=RealtimeRuleSession(
            engine,
            session_id="live-test",
        ),
    )
    update = runtime.process_frame_set(_frame_set())
    assert update.trace.actions[0].action.value == "PICK"
    assert update.rule_updates[-1].result.steps[0].state.value == "COMPLETED"
