from video_pose.live_health import LiveHealthRegistry
from video_pose.live_runtime import LiveAnalysisRuntime
from video_pose.video_manifest import CameraPosition
from video_pose.video_replay import FrameRef, SynchronizedFrameSet


class FakeGateway:
    def start(self, _callback: object) -> None:
        pass

    def stop(self) -> None:
        pass


class FakePipeline:
    pass


class FakeRuleSession:
    pass


def _frame_set(timestamp: float) -> SynchronizedFrameSet:
    ref = FrameRef(
        camera_id="front",
        position=CameraPosition.FRONT,
        uri=f"memory://front/{timestamp}",
        source_timestamp_ms=timestamp,
        normalized_timestamp_ms=timestamp,
    )
    return SynchronizedFrameSet(
        reference_timestamp_ms=timestamp,
        frames={CameraPosition.FRONT: ref},
        skew_ms=0,
    )


def test_backpressure_drops_oldest_frame_set() -> None:
    health = LiveHealthRegistry(["front"], queue_capacity=1)
    runtime = LiveAnalysisRuntime(
        gateway=FakeGateway(),  # type: ignore[arg-type]
        pipeline=FakePipeline(),  # type: ignore[arg-type]
        rule_session=FakeRuleSession(),  # type: ignore[arg-type]
        health=health,
        processing_queue_size=1,
    )

    runtime.enqueue_frame_set(_frame_set(100))
    runtime.enqueue_frame_set(_frame_set(200))

    snapshot = health.snapshot()
    assert snapshot.runtime.frame_sets_received_total == 2
    assert snapshot.runtime.frame_sets_dropped_total == 1
    assert snapshot.runtime.queue_depth == 1
