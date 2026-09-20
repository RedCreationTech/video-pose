from __future__ import annotations

import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path

from pydantic import BaseModel, Field

from .live_evidence import LiveEvidenceManifest
from .violation_review import ReviewStatus


class EvidenceRetentionPolicy(BaseModel):
    retention_days: int = Field(default=180, ge=1)
    max_total_bytes: int = Field(default=50 * 1024**3, ge=1)
    protect_unreviewed: bool = True


class EvidenceRetentionReport(BaseModel):
    deleted_count: int
    deleted_bytes: int
    protected_count: int
    total_bytes_after: int
    over_capacity: bool


class EvidenceRetentionStatus(BaseModel):
    artifact_count: int
    protected_count: int
    total_bytes: int
    max_total_bytes: int
    over_capacity: bool


class _EvidenceDirectory(BaseModel):
    directory: Path
    manifest: LiveEvidenceManifest
    size_bytes: int
    created_at: datetime


class EvidenceRetentionManager:
    """Delete old reviewed evidence while protecting pending review items."""

    def __init__(
        self,
        root: str | Path,
        policy: EvidenceRetentionPolicy | None = None,
    ) -> None:
        self.root = Path(root)
        self.policy = policy or EvidenceRetentionPolicy()

    def status(self) -> EvidenceRetentionStatus:
        entries = self._entries()
        total = sum(entry.size_bytes for entry in entries)
        protected_count = sum(
            1 for entry in entries if self._protected(entry)
        )
        return EvidenceRetentionStatus(
            artifact_count=len(entries),
            protected_count=protected_count,
            total_bytes=total,
            max_total_bytes=self.policy.max_total_bytes,
            over_capacity=total > self.policy.max_total_bytes,
        )

    def cleanup(
        self,
        *,
        now: datetime | None = None,
    ) -> EvidenceRetentionReport:
        current = now or datetime.now(UTC)
        entries = self._entries()
        total = sum(entry.size_bytes for entry in entries)
        deleted_count = 0
        deleted_bytes = 0
        protected_count = 0
        deleted: set[Path] = set()

        cutoff = current - timedelta(days=self.policy.retention_days)
        for entry in sorted(entries, key=lambda item: item.created_at):
            if self._protected(entry):
                protected_count += 1
                continue
            if entry.created_at >= cutoff:
                continue
            self._delete(entry)
            deleted.add(entry.directory)
            total -= entry.size_bytes
            deleted_count += 1
            deleted_bytes += entry.size_bytes

        if total > self.policy.max_total_bytes:
            for entry in sorted(entries, key=lambda item: item.created_at):
                if entry.directory in deleted:
                    continue
                if self._protected(entry):
                    continue
                self._delete(entry)
                deleted.add(entry.directory)
                total -= entry.size_bytes
                deleted_count += 1
                deleted_bytes += entry.size_bytes
                if total <= self.policy.max_total_bytes:
                    break

        return EvidenceRetentionReport(
            deleted_count=deleted_count,
            deleted_bytes=deleted_bytes,
            protected_count=protected_count,
            total_bytes_after=max(0, total),
            over_capacity=total > self.policy.max_total_bytes,
        )

    def _entries(self) -> list[_EvidenceDirectory]:
        if not self.root.exists():
            return []
        output: list[_EvidenceDirectory] = []
        for manifest_path in self.root.glob("*/*/manifest.json"):
            try:
                manifest = LiveEvidenceManifest.model_validate_json(
                    manifest_path.read_text(encoding="utf-8")
                )
                created_at = datetime.fromisoformat(manifest.created_at)
                if created_at.tzinfo is None:
                    created_at = created_at.replace(tzinfo=UTC)
                directory = manifest_path.parent
                size_bytes = sum(
                    path.stat().st_size
                    for path in directory.rglob("*")
                    if path.is_file()
                )
                output.append(
                    _EvidenceDirectory(
                        directory=directory,
                        manifest=manifest,
                        size_bytes=size_bytes,
                        created_at=created_at,
                    )
                )
            except Exception:
                continue
        return output

    def _protected(self, entry: _EvidenceDirectory) -> bool:
        return (
            self.policy.protect_unreviewed
            and entry.manifest.review_status == ReviewStatus.UNREVIEWED
        )

    @staticmethod
    def _delete(entry: _EvidenceDirectory) -> None:
        shutil.rmtree(entry.directory)
