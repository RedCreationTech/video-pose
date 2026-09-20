from pathlib import Path

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


def _frame_set(timestamp: float) -> SynchronizedFrameSet:
    frames = {}
    for position in CameraPosition:
        camera_id = position.value.lower()
        frames[position] = FrameRef(
            camera_id=camera_id,
            position=position,
            uri=f"{camera_id}-{timestamp}",
            source_timestamp_ms=timestamp,
            normalized_timestamp_ms=timestamp,
        )
    return SynchronizedFrameSet(
        reference_timestamp_ms=timestamp,
        frames=frames,
        skew_ms=0,
    )


def test_live_evidence_collects_pre_and_post_roll(tmp_path: Path) -> None:
    buffer = LiveEvidenceBuffer(
        root=tmp_path,
        encoder=FakeEncoder(),
        camera_ids=["front", "rear", "left", "right"],
        pre_roll_ms=1000,
        post_roll_ms=1000,
        sample_interval_ms=1,
    )
    loader = FakeLoader()
    buffer.ingest(_frame_set(0), loader)
    buffer.ingest(_frame_set(1000), loader)
    evidence_id = buffer.schedule(
        "session-1",
        {
            "rule_id": "R1",
            "step": "S010",
            "event_id": "a1",
            "type": "SPATIAL",
        },
        timestamp_ms=1000,
    )
    finalized = buffer.ingest(_frame_set(2000), loader)
    assert len(finalized) == 1
    manifest = finalized[0]
    assert manifest.evidence_id == evidence_id
    assert manifest.status == "COMPLETE"
    assert len(manifest.images) == 12
    assert set(manifest.cameras_present) == {
        "front",
        "rear",
        "left",
        "right",
    }
    assert buffer.get_manifest("session-1", evidence_id) is not None


def test_live_evidence_deduplicates_same_violation(tmp_path: Path) -> None:
    buffer = LiveEvidenceBuffer(
        root=tmp_path,
        encoder=FakeEncoder(),
        camera_ids=["front"],
        pre_roll_ms=0,
        post_roll_ms=0,
        sample_interval_ms=1,
    )
    violation = {
        "rule_id": "R1",
        "step": "S010",
        "event_id": "a1",
        "type": "ORDER",
    }
    first = buffer.schedule("s1", violation, timestamp_ms=100)
    second = buffer.schedule("s1", violation, timestamp_ms=100)
    assert first == second


def test_flush_marks_incomplete_capture_partial(tmp_path: Path) -> None:
    buffer = LiveEvidenceBuffer(
        root=tmp_path,
        encoder=FakeEncoder(),
        camera_ids=["front", "rear"],
        pre_roll_ms=1000,
        post_roll_ms=1000,
        sample_interval_ms=1,
    )
    buffer.ingest(
        SynchronizedFrameSet(
            reference_timestamp_ms=1000,
            frames={
                CameraPosition.FRONT: FrameRef(
                    camera_id="front",
                    position=CameraPosition.FRONT,
                    uri="front",
                    source_timestamp_ms=1000,
                    normalized_timestamp_ms=1000,
                )
            },
            skew_ms=0,
        ),
        FakeLoader(),
    )
    buffer.schedule(
        "s1",
        {
            "rule_id": "R1",
            "step": "S1",
            "event_id": "a1",
            "type": "TIMEOUT",
        },
        timestamp_ms=1000,
    )
    manifest = buffer.flush_pending()[0]
    assert manifest.status == "PARTIAL"
    assert manifest.cameras_present == ["front"]
