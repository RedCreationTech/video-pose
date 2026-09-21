from __future__ import annotations

import json
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from .live_health import AuditHealthSnapshot


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


class SessionAuditMetadata(BaseModel):
    session_id: str
    trace_id: str | None = None
    operator_id: str | None = None
    operation: str
    workstation_id: str
    rule_set_version: int
    started_at: str
    config_path: str
    detector_weights: str
    pose_config: str | None = None
    pose_checkpoint: str | None = None
    planar_calibration: str | None = None
    perspective_calibration: str | None = None
    capture_backend: str | None = None
    timestamp_source: str | None = None
    sync_tolerance_ms: float | None = None
    camera_clock_offsets_ms: dict[str, float] = Field(
        default_factory=dict
    )
    config_sha256: str | None = None
    manifest_sha256: str | None = None
    rules_sha256: str | None = None
    zones_sha256: str | None = None
    planar_calibration_sha256: str | None = None
    perspective_calibration_sha256: str | None = None
    calibration_health_profile_sha256: str | None = None
    calibration_control_points_sha256: str | None = None
    pose_config_sha256: str | None = None
    model_release_id: str | None = None
    model_release_manifest_sha256: str | None = None
    model_artifact_sha256: dict[str, str] = Field(
        default_factory=dict
    )
    application_version: str | None = None
    git_sha: str | None = None
    image_digest: str | None = None
    release_fingerprint: str | None = None


class SessionAuditWriter:
    """Durable JSON/JSONL audit writer with observable write health."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self._lock = threading.RLock()
        self._write_errors_total = 0
        self._last_error: str | None = None
        self._last_success_at: str | None = None

    def health(self) -> AuditHealthSnapshot:
        with self._lock:
            return AuditHealthSnapshot(
                status=(
                    "DEGRADED"
                    if self._last_error is not None
                    else "READY"
                ),
                write_errors_total=self._write_errors_total,
                last_error=self._last_error,
                last_success_at=self._last_success_at,
            )

    def probe(self) -> AuditHealthSnapshot:
        with self._lock:
            probe = self.root / ".video-pose-audit-probe"
            try:
                self.root.mkdir(parents=True, exist_ok=True)
                probe.write_text("ok\n", encoding="utf-8")
                probe.unlink(missing_ok=True)
            except Exception as exc:
                self._record_error_unlocked(exc)
                raise
            self._record_success_unlocked()
            return self.health()

    def start(self, metadata: SessionAuditMetadata) -> Path:
        directory = self.root / metadata.session_id
        with self._lock:
            try:
                directory.mkdir(parents=True, exist_ok=False)
                self._write_json_unlocked(
                    directory / "metadata.json",
                    metadata.model_dump(mode="json"),
                )
                (directory / "updates.jsonl").touch()
                (directory / "reviews.jsonl").touch()
            except Exception as exc:
                self._record_error_unlocked(exc)
                raise
            self._record_success_unlocked()
        return directory

    def append_payload(
        self,
        session_id: str,
        payload: dict[str, Any],
    ) -> None:
        record = {
            "recorded_at": _utc_now(),
            "payload": payload,
        }
        path = self.root / session_id / "updates.jsonl"
        rendered = json.dumps(
            record,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        with self._lock:
            try:
                with path.open("a", encoding="utf-8") as handle:
                    handle.write(rendered + "\n")
            except Exception as exc:
                self._record_error_unlocked(exc)
                raise
            self._record_success_unlocked()

    def append_review(
        self,
        session_id: str,
        payload: dict[str, Any],
    ) -> None:
        record = {
            "recorded_at": _utc_now(),
            "payload": payload,
        }
        path = self.root / session_id / "reviews.jsonl"
        rendered = json.dumps(
            record,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        with self._lock:
            try:
                with path.open("a", encoding="utf-8") as handle:
                    handle.write(rendered + "\n")
            except Exception as exc:
                self._record_error_unlocked(exc)
                raise
            self._record_success_unlocked()

    def finish(
        self,
        session_id: str,
        final_payload: dict[str, Any],
        *,
        status: str,
    ) -> Path:
        path = self.root / session_id / "final.json"
        payload = {
            "status": status,
            "ended_at": _utc_now(),
            "result": final_payload,
        }
        with self._lock:
            try:
                self._write_json_unlocked(path, payload)
            except Exception as exc:
                self._record_error_unlocked(exc)
                raise
            self._record_success_unlocked()
        return path

    @staticmethod
    def _write_json_unlocked(
        path: Path,
        payload: dict[str, Any],
    ) -> None:
        rendered = json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
        )
        path.write_text(rendered + "\n", encoding="utf-8")

    def _record_success_unlocked(self) -> None:
        self._last_error = None
        self._last_success_at = _utc_now()

    def _record_error_unlocked(self, exc: Exception) -> None:
        self._write_errors_total += 1
        self._last_error = str(exc)
