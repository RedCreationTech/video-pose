from video_pose.live_health import LiveHealthRegistry
from video_pose.live_video import MemoryFrameStore
from video_pose.persistent_camera import PersistentCameraHub
from video_pose.video_manifest import CameraPosition, ReplayManifest
from video_pose.video_replay import FrameRef, SynchronizedFrameSet


class FakeGateway:
    def __init__(self) -> None:
        self.start_calls = 0
        self.stop_calls = 0
        self.callback = None

    def start(self, callback) -> None:
        self.start_calls += 1
        self.callback = callback

    def stop(self) -> None:
        self.stop_calls += 1

    def emit(self, frame_set: SynchronizedFrameSet) -> None:
        assert self.callback is not None
        self.callback(frame_set)


def _manifest() -> ReplayManifest:
    return ReplayManifest.model_validate(
        {
            "session_id": "hub",
            "workstation_id": "ws-1",
            "cameras": [
                {"camera_id": "f", "position": "FRONT", "uri": "rtsp://f"},
                {"camera_id": "r", "position": "REAR", "uri": "rtsp://r"},
                {"camera_id": "l", "position": "LEFT", "uri": "rtsp://l"},
                {"camera_id": "x", "position": "RIGHT", "uri": "rtsp://x"},
            ],
        }
    )


def _frame(timestamp: float) -> SynchronizedFrameSet:
    ref = FrameRef(
        camera_id="f",
        position=CameraPosition.FRONT,
        uri=f"memory://f/{timestamp}",
        source_timestamp_ms=timestamp,
        normalized_timestamp_ms=timestamp,
    )
    return SynchronizedFrameSet(
        reference_timestamp_ms=timestamp,
        frames={CameraPosition.FRONT: ref},
        skew_ms=0,
    )


def test_persistent_hub_does_not_replay_old_frames_to_new_subscriber() -> None:
    gateway = FakeGateway()
    hub = PersistentCameraHub(
        manifest=_manifest(),
        frame_store=MemoryFrameStore(),
        health=LiveHealthRegistry(["f", "r", "l", "x"]),
        gateway=gateway,  # type: ignore[arg-type]
    )
    hub.start()
    hub.start()
    gateway.emit(_frame(100))

    received = []
    token = hub.subscribe(received.append)
    gateway.emit(_frame(200))
    hub.unsubscribe(token)
    gateway.emit(_frame(300))
    hub.stop()

    assert gateway.start_calls == 1
    assert gateway.stop_calls == 1
    assert [item.reference_timestamp_ms for item in received] == [200]
    assert hub.health_snapshot().runtime.frame_sets_received_total == 3
