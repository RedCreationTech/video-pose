from datetime import UTC, datetime
from pathlib import Path

from video_pose.evidence_retention import (
    EvidenceRetentionManager,
    EvidenceRetentionPolicy,
)
from video_pose.live_evidence import LiveEvidenceManifest


def _write_evidence(
    root: Path,
    evidence_id: str,
    review_status: str,
    created_at: str,
    size: int,
) -> None:
    directory = root / "s1" / evidence_id
    directory.mkdir(parents=True)
    manifest = LiveEvidenceManifest(
        evidence_id=evidence_id,
        session_id="s1",
        status="COMPLETE",
        violation_type="SPATIAL",
        rule_id=evidence_id,
        step_code="S1",
        event_id="a1",
        normalized_start_ms=0,
        normalized_end_ms=1,
        created_at=created_at,
        review_status=review_status,
        cameras_expected=["front"],
        cameras_present=["front"],
    )
    (directory / "manifest.json").write_text(
        manifest.model_dump_json(indent=2),
        encoding="utf-8",
    )
    (directory / "payload.bin").write_bytes(b"x" * size)


def test_retention_deletes_old_reviewed_but_protects_unreviewed(
    tmp_path: Path,
) -> None:
    old = "2025-01-01T00:00:00+00:00"
    _write_evidence(tmp_path, "reviewed", "CONFIRMED", old, 100)
    _write_evidence(tmp_path, "pending", "UNREVIEWED", old, 100)

    manager = EvidenceRetentionManager(
        tmp_path,
        EvidenceRetentionPolicy(
            retention_days=30,
            max_total_bytes=10_000,
            protect_unreviewed=True,
        ),
    )
    report = manager.cleanup(
        now=datetime(2026, 9, 21, tzinfo=UTC)
    )
    assert report.deleted_count == 1
    assert not (tmp_path / "s1" / "reviewed").exists()
    assert (tmp_path / "s1" / "pending").exists()


def test_capacity_cleanup_keeps_unreviewed_even_when_over_limit(
    tmp_path: Path,
) -> None:
    recent = "2026-09-20T00:00:00+00:00"
    _write_evidence(tmp_path, "pending", "UNREVIEWED", recent, 500)
    manager = EvidenceRetentionManager(
        tmp_path,
        EvidenceRetentionPolicy(
            retention_days=365,
            max_total_bytes=100,
            protect_unreviewed=True,
        ),
    )
    report = manager.cleanup(
        now=datetime(2026, 9, 21, tzinfo=UTC)
    )
    assert report.deleted_count == 0
    assert report.over_capacity is True
