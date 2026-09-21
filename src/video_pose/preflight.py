from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from .live_health import LiveHealthSnapshot
from .session_readiness import SessionReadinessReport


class PreflightCheck(BaseModel):
    name: str
    passed: bool
    status: str


class PreflightCamera(BaseModel):
    camera_id: str
    position: str
    enabled: bool
    state: str
    fps: float
    reconnect_total: int
    capture_backend: str
    timestamp_source: str
    snapshot_available: bool


class PreflightStorage(BaseModel):
    name: str
    free_ratio: float
    free_gb: float


class PreflightPersistence(BaseModel):
    configured: bool
    connectivity: str
    write_errors_total: int | None = None
    read_errors_total: int | None = None
    reconciliation: str | None = None
    repaired_count: int | None = None
    failed_count: int | None = None
    incomplete_count: int | None = None


class PreflightRelease(BaseModel):
    application_version: str
    git_sha: str
    image_digest: str | None = None
    release_fingerprint: str | None = None
    model_release_id: str | None = None


class PreflightReport(BaseModel):
    generated_at: str
    workstation_id: str
    ready: bool
    failed_checks: list[str] = Field(default_factory=list)
    checks: list[PreflightCheck] = Field(default_factory=list)
    cameras: list[PreflightCamera] = Field(default_factory=list)
    release: PreflightRelease
    model_warmup_status: str | None = None
    model_warmup_latency_ms: float | None = None
    sync_emitted_total: int | None = None
    sync_miss_ratio: float | None = None
    sync_p99_skew_ms: float | None = None
    max_abs_sync_drift_ms_per_minute: float | None = None
    evidence_errors_total: int | None = None
    evidence_drop_ratio: float | None = None
    evidence_over_capacity: bool | None = None
    audit_status: str | None = None
    audit_write_errors_total: int | None = None
    storage: list[PreflightStorage] = Field(default_factory=list)
    persistence: PreflightPersistence


def build_preflight_report(
    *,
    workstation_id: str,
    readiness: SessionReadinessReport,
    health: LiveHealthSnapshot,
    cameras: list[dict[str, Any]],
    release_identity: dict[str, Any],
    persistence: dict[str, Any],
) -> PreflightReport:
    sync = health.sync
    max_drift = None
    sync_miss_ratio = None
    if sync is not None:
        attempts = sync.reference_frames_total
        sync_miss_ratio = (
            sync.miss_total / attempts if attempts else 0.0
        )
        max_drift = max(
            (
                abs(value)
                for value in sync.camera_drift_ms_per_minute.values()
            ),
            default=0.0,
        )

    warmup = health.model_warmup
    evidence = health.evidence
    audit = health.audit
    runtime_fingerprint = release_identity.get(
        "runtime_fingerprint"
    )
    if not isinstance(runtime_fingerprint, dict):
        runtime_fingerprint = {}

    reconciliation = persistence.get("reconciliation")
    if not isinstance(reconciliation, dict):
        reconciliation = {}

    checks = [
        PreflightCheck(
            name=item.name,
            passed=item.passed,
            status="PASS" if item.passed else "FAIL",
        )
        for item in readiness.checks
    ]

    return PreflightReport(
        generated_at=datetime.now(UTC).isoformat(),
        workstation_id=workstation_id,
        ready=readiness.ready,
        failed_checks=[
            item.name
            for item in readiness.checks
            if not item.passed
        ],
        checks=checks,
        cameras=[
            PreflightCamera(
                camera_id=str(item.get("camera_id", "")),
                position=str(item.get("position", "")),
                enabled=bool(item.get("enabled", False)),
                state=str(item.get("state", "UNKNOWN")),
                fps=float(item.get("fps", 0.0)),
                reconnect_total=int(
                    item.get("reconnect_total", 0)
                ),
                capture_backend=str(
                    item.get("capture_backend", "")
                ),
                timestamp_source=str(
                    item.get("timestamp_source", "")
                ),
                snapshot_available=bool(
                    item.get("snapshot_available", False)
                ),
            )
            for item in cameras
        ],
        release=PreflightRelease(
            application_version=str(
                release_identity.get(
                    "application_version",
                    "unknown",
                )
            ),
            git_sha=str(
                release_identity.get("git_sha", "unknown")
            ),
            image_digest=release_identity.get(
                "image_digest"
            ),
            release_fingerprint=release_identity.get(
                "release_fingerprint"
            ),
            model_release_id=runtime_fingerprint.get(
                "model_release_id"
            ),
        ),
        model_warmup_status=(
            warmup.status if warmup is not None else None
        ),
        model_warmup_latency_ms=(
            warmup.latency_ms if warmup is not None else None
        ),
        sync_emitted_total=(
            sync.emitted_total if sync is not None else None
        ),
        sync_miss_ratio=sync_miss_ratio,
        sync_p99_skew_ms=(
            sync.skew_p99_ms if sync is not None else None
        ),
        max_abs_sync_drift_ms_per_minute=max_drift,
        evidence_errors_total=(
            evidence.errors_total
            if evidence is not None
            else None
        ),
        evidence_drop_ratio=(
            evidence.drop_ratio
            if evidence is not None
            else None
        ),
        evidence_over_capacity=(
            evidence.over_capacity
            if evidence is not None
            else None
        ),
        audit_status=(
            audit.status if audit is not None else None
        ),
        audit_write_errors_total=(
            audit.write_errors_total
            if audit is not None
            else None
        ),
        storage=[
            PreflightStorage(
                name=item.name,
                free_ratio=item.free_ratio,
                free_gb=item.free_bytes / (1024**3),
            )
            for item in health.storage
        ],
        persistence=PreflightPersistence(
            configured=bool(
                persistence.get("configured", False)
            ),
            connectivity=str(
                persistence.get("status", "DISABLED")
            ),
            write_errors_total=persistence.get(
                "write_errors_total"
            ),
            read_errors_total=persistence.get(
                "read_errors_total"
            ),
            reconciliation=(
                str(reconciliation.get("status"))
                if reconciliation.get("status") is not None
                else None
            ),
            repaired_count=reconciliation.get(
                "repaired_count"
            ),
            failed_count=reconciliation.get(
                "failed_count"
            ),
            incomplete_count=reconciliation.get(
                "incomplete_count"
            ),
        ),
    )
