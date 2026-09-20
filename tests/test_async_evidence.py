import threading

from video_pose.async_evidence import AsyncLiveEvidenceRecorder
from video_pose.frames import DecodedFrame
from video_pose.live_evidence import LiveEvidenceBuffer
from video_pose.video_manifest import CameraPosition
from video_pose.video_replay import FrameRef, SynchronizedFrameSet


class FakeEncoder:
    def encode(self, image):
        return f"jpeg:{image}".encode()


class FakeLoader:
    def load(self, ref):
        return DecodedFrame(ref=ref, image=ref.uri)


def _frame_set(timestamp):
    ref = FrameRef(
        camera_id="front",
        position=CameraPosition.FRONT,
        uri=f"frame-{timestamp}",
        source_timestamp_ms=timestamp,
        normalized_timestamp_ms=timestamp,
    )
    return SynchronizedFrameSet(
        reference_timestamp_ms=timestamp,
        frames={CameraPosition.FRONT: ref},
        skew_ms=0,
    )


def test_async_evidence_recorder_preserves_capture_window(tmp_path):
    buffer = LiveEvidenceBuffer(
        root=tmp_path,
        encoder=FakeEncoder(),
        camera_ids=["front"],
        pre_roll_ms=1000,
        post_roll_ms=1000,
        sample_interval_ms=1,
    )
    recorder = AsyncLiveEvidenceRecorder(buffer, queue_size=2)
    recorder.start()
    recorder.submit(_frame_set(0), FakeLoader())
    recorder.submit(_frame_set(1000), FakeLoader())
    recorder.wait_until_idle()

    evidence_id = recorder.schedule(
        "s1",
        {
            "rule_id": "R1",
            "step": "S1",
            "event_id": "a1",
            "type": "SPATIAL",
        },
        timestamp_ms=1000,
    )
    recorder.submit(_frame_set(2000), FakeLoader())
    recorder.wait_until_idle()

    manifest = recorder.get_manifest("s1", evidence_id)
    assert manifest is not None
    assert manifest.status == "COMPLETE"
    assert len(manifest.images) == 3
    stats = recorder.stats()
    assert stats.processed_total == 3
    assert stats.errors_total == 0
    recorder.stop()


class BlockingBuffer:
    def __init__(self):
        self.started = threading.Event()
        self.release = threading.Event()

    def ingest(self, _frame_set, _loader):
        self.started.set()
        self.release.wait(timeout=2)

    def flush_pending(self):
        return []

    def schedule(self, session_id, violation, *, timestamp_ms):
        del session_id, violation, timestamp_ms
        return "ev"

    def list_session(self, _session_id):
        return []

    def get_manifest(self, _session_id, _evidence_id):
        return None

    def read_file(self, *_args):
        return b""


def test_async_evidence_drops_oldest_when_queue_is_full():
    buffer = BlockingBuffer()
    recorder = AsyncLiveEvidenceRecorder(buffer, queue_size=1)
    recorder.start()
    recorder.submit(_frame_set(0), FakeLoader())
    assert buffer.started.wait(timeout=1)
    recorder.submit(_frame_set(100), FakeLoader())
    recorder.submit(_frame_set(200), FakeLoader())
    assert recorder.stats().dropped_total == 1
    buffer.release.set()
    recorder.wait_until_idle()
    recorder.stop()
