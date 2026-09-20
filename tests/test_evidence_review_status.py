from video_pose.frames import DecodedFrame
from video_pose.live_evidence import LiveEvidenceBuffer
from video_pose.video_manifest import CameraPosition
from video_pose.video_replay import FrameRef, SynchronizedFrameSet


class FakeEncoder:
    def encode(self, image):
        return str(image).encode()


class FakeLoader:
    def load(self, ref):
        return DecodedFrame(ref=ref, image=ref.uri)


def _frame(timestamp):
    ref = FrameRef(
        camera_id="front",
        position=CameraPosition.FRONT,
        uri=f"f-{timestamp}",
        source_timestamp_ms=timestamp,
        normalized_timestamp_ms=timestamp,
    )
    return SynchronizedFrameSet(
        reference_timestamp_ms=timestamp,
        frames={CameraPosition.FRONT: ref},
        skew_ms=0,
    )


def test_review_status_applies_when_review_precedes_finalize(tmp_path):
    buffer = LiveEvidenceBuffer(
        root=tmp_path,
        encoder=FakeEncoder(),
        camera_ids=["front"],
        pre_roll_ms=0,
        post_roll_ms=100,
        sample_interval_ms=1,
    )
    buffer.ingest(_frame(100), FakeLoader())
    evidence_id = buffer.schedule(
        "s1",
        {
            "rule_id": "R1",
            "step": "S1",
            "event_id": "a1",
            "type": "ORDER",
        },
        timestamp_ms=100,
    )
    buffer.mark_reviewed(
        "s1",
        rule_id="R1",
        step_code="S1",
        event_id="a1",
        status="CONFIRMED",
        reviewed_at="2026-09-21T00:00:00+00:00",
    )
    buffer.ingest(_frame(200), FakeLoader())
    manifest = buffer.get_manifest("s1", evidence_id)
    assert manifest is not None
    assert manifest.review_status == "CONFIRMED"


def test_review_status_updates_existing_manifest(tmp_path):
    buffer = LiveEvidenceBuffer(
        root=tmp_path,
        encoder=FakeEncoder(),
        camera_ids=["front"],
        pre_roll_ms=0,
        post_roll_ms=0,
        sample_interval_ms=1,
    )
    buffer.ingest(_frame(100), FakeLoader())
    evidence_id = buffer.schedule(
        "s1",
        {
            "rule_id": "R1",
            "step": "S1",
            "event_id": "a1",
            "type": "ORDER",
        },
        timestamp_ms=100,
    )
    buffer.ingest(_frame(100), FakeLoader())
    buffer.mark_reviewed(
        "s1",
        rule_id="R1",
        step_code="S1",
        event_id="a1",
        status="DISMISSED",
        reviewed_at="2026-09-21T00:00:00+00:00",
    )
    manifest = buffer.get_manifest("s1", evidence_id)
    assert manifest is not None
    assert manifest.review_status == "DISMISSED"
