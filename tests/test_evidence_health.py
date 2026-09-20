from pathlib import Path

from video_pose.async_evidence import AsyncLiveEvidenceRecorder
from video_pose.evidence_retention import (
    EvidenceRetentionManager,
    EvidenceRetentionPolicy,
)
from video_pose.live_evidence import LiveEvidenceBuffer


class FakeEncoder:
    def encode(self, image):
        return str(image).encode()


def test_evidence_health_includes_worker_and_retention_state(
    tmp_path: Path,
) -> None:
    buffer = LiveEvidenceBuffer(
        root=tmp_path,
        encoder=FakeEncoder(),
        camera_ids=["front"],
    )
    retention = EvidenceRetentionManager(
        tmp_path,
        EvidenceRetentionPolicy(max_total_bytes=1024),
    )
    recorder = AsyncLiveEvidenceRecorder(
        buffer,
        queue_size=2,
        retention=retention,
        status_refresh_interval_s=60,
    )
    health = recorder.health_snapshot()
    assert health.queue_capacity == 2
    assert health.artifact_count == 0
    assert health.total_bytes == 0
    assert health.max_total_bytes == 1024
    assert health.over_capacity is False
