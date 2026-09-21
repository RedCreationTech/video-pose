from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel

from .live_health import CameraState
from .runtime_config import LoadedAnalysisConfig
from .storage_health import sample_runtime_storage


class SessionReadinessCheck(BaseModel):
    name: str
    passed: bool
    detail: str


class SessionReadinessReport(BaseModel):
    policy_enabled: bool
    ready: bool
    checks: list[SessionReadinessCheck]


class SessionNotReadyError(RuntimeError):
    def __init__(self, report: SessionReadinessReport) -> None:
        self.report = report
        failed = [
            check.name
            for check in report.checks
            if not check.passed
        ]
        detail = ", ".join(failed) or "unknown"
        super().__init__(
            "session is not ready: " + detail
        )


def _check(
    checks: list[SessionReadinessCheck],
    name: str,
    passed: bool,
    detail: str,
) -> None:
    checks.append(
        SessionReadinessCheck(
            name=name,
            passed=passed,
            detail=detail,
        )
    )


def _asset_check(
    config: LoadedAnalysisConfig,
    checks: list[SessionReadinessCheck],
    name: str,
    value: str | None,
    *,
    required: bool,
) -> None:
    if value is None:
        _check(
            checks,
            name,
            not required,
            "not configured",
        )
        return
    path = config.resolve(value)
    _check(
        checks,
        name,
        path.is_file(),
        str(path),
    )


def _persistence_status(repository: Any) -> tuple[str, str]:
    if repository is None:
        return "DISABLED", "repository is not configured"
    health_method = getattr(repository, "health", None)
    if not callable(health_method):
        return "READY", "repository has no degraded health interface"
    health = health_method()
    raw_status = getattr(health, "status", "READY")
    status = getattr(raw_status, "value", str(raw_status))
    last_error = getattr(health, "last_error", None)
    return status, str(last_error or status)


def evaluate_session_readiness(
    config: LoadedAnalysisConfig,
    *,
    hub: Any,
    model_pool: Any | None,
    repository: Any | None,
    audit_root: str | Path | None = None,
) -> SessionReadinessReport:
    policy = config.config.readiness
    if not policy.enabled:
        return SessionReadinessReport(
            policy_enabled=False,
            ready=True,
            checks=[
                SessionReadinessCheck(
                    name="policy",
                    passed=True,
                    detail="session readiness policy is disabled",
                )
            ],
        )

    checks: list[SessionReadinessCheck] = []
    running = bool(getattr(hub, "running", False))
    _check(
        checks,
        "camera-hub",
        running,
        "running" if running else "not running",
    )

    if model_pool is not None:
        loaded = bool(getattr(model_pool, "loaded", False))
        _check(
            checks,
            "model-pool",
            loaded,
            "loaded" if loaded else "not loaded",
        )

    snapshot = hub.health_snapshot()
    state_by_id = {
        camera.camera_id: camera.state
        for camera in snapshot.cameras
    }
    expected_cameras = [
        camera.camera_id
        for camera in getattr(hub.manifest, "cameras", [])
        if getattr(camera, "enabled", True)
    ]
    if policy.require_all_cameras_online:
        acceptable = {CameraState.ONLINE}
        if policy.allow_camera_degraded:
            acceptable.add(CameraState.DEGRADED)
        bad = {
            camera_id: (
                state_by_id[camera_id].value
                if camera_id in state_by_id
                else "MISSING"
            )
            for camera_id in expected_cameras
            if (
                camera_id not in state_by_id
                or state_by_id[camera_id] not in acceptable
            )
        }
        _check(
            checks,
            "cameras",
            not bad,
            "all cameras ready" if not bad else str(bad),
        )

    if policy.require_sync:
        sync = snapshot.sync
        if sync is None:
            _check(
                checks,
                "sync",
                False,
                "sync health is unavailable",
            )
        else:
            attempts = sync.reference_frames_total
            miss_ratio = (
                sync.miss_total / attempts if attempts else 0.0
            )
            max_drift = max(
                (
                    abs(value)
                    for value in sync.camera_drift_ms_per_minute.values()
                ),
                default=0.0,
            )
            _check(
                checks,
                "sync-warmup",
                sync.emitted_total >= policy.min_sync_emitted_total,
                (
                    f"emitted={sync.emitted_total}, "
                    f"required={policy.min_sync_emitted_total}"
                ),
            )
            _check(
                checks,
                "sync-miss-ratio",
                miss_ratio <= policy.max_sync_miss_ratio,
                (
                    f"miss_ratio={miss_ratio:.6f}, "
                    f"max={policy.max_sync_miss_ratio:.6f}"
                ),
            )
            _check(
                checks,
                "sync-p99-skew",
                sync.skew_p99_ms <= policy.max_sync_p99_skew_ms,
                (
                    f"p99={sync.skew_p99_ms:.3f}ms, "
                    f"max={policy.max_sync_p99_skew_ms:.3f}ms"
                ),
            )
            _check(
                checks,
                "sync-clock-drift",
                max_drift
                <= policy.max_abs_sync_drift_ms_per_minute,
                (
                    f"max_abs={max_drift:.6f}ms/min, "
                    "max="
                    f"{policy.max_abs_sync_drift_ms_per_minute:.6f}"
                    "ms/min"
                ),
            )

    if config.config.evidence.enabled:
        evidence = snapshot.evidence
        if evidence is None:
            _check(
                checks,
                "evidence",
                False,
                "evidence health is unavailable",
            )
        else:
            if policy.block_evidence_over_capacity:
                _check(
                    checks,
                    "evidence-capacity",
                    not evidence.over_capacity,
                    (
                        f"bytes={evidence.total_bytes}, "
                        f"limit={evidence.max_total_bytes}, "
                        f"over_capacity={evidence.over_capacity}"
                    ),
                )
            if policy.block_evidence_errors:
                _check(
                    checks,
                    "evidence-errors",
                    evidence.errors_total == 0,
                    f"errors_total={evidence.errors_total}",
                )

    if policy.require_runtime_assets:
        cfg = config.config
        _asset_check(
            config,
            checks,
            "asset:rules",
            cfg.rules,
            required=True,
        )
        _asset_check(
            config,
            checks,
            "asset:manifest",
            cfg.manifest,
            required=True,
        )
        _asset_check(
            config,
            checks,
            "asset:zones",
            cfg.zones,
            required=False,
        )
        _asset_check(
            config,
            checks,
            "asset:planar-calibration",
            cfg.calibration,
            required=False,
        )
        _asset_check(
            config,
            checks,
            "asset:perspective-calibration",
            (
                cfg.triangulation.calibration
                if cfg.triangulation.enabled
                else None
            ),
            required=cfg.triangulation.enabled,
        )

    if policy.require_storage_headroom and audit_root is not None:
        storage = sample_runtime_storage(
            config,
            audit_root=audit_root,
        )
        if not storage:
            _check(
                checks,
                "storage",
                False,
                "storage health is unavailable",
            )
        for volume in storage:
            free_gb = volume.free_bytes / (1024**3)
            _check(
                checks,
                f"storage:{volume.name}:free-ratio",
                volume.free_ratio >= policy.min_storage_free_ratio,
                (
                    f"free_ratio={volume.free_ratio:.6f}, "
                    f"min={policy.min_storage_free_ratio:.6f}"
                ),
            )
            _check(
                checks,
                f"storage:{volume.name}:free-gb",
                free_gb >= policy.min_storage_free_gb,
                (
                    f"free_gb={free_gb:.3f}, "
                    f"min={policy.min_storage_free_gb:.3f}"
                ),
            )

    persistence_status, persistence_detail = _persistence_status(
        repository
    )
    if policy.require_persistence:
        _check(
            checks,
            "persistence-configured",
            repository is not None,
            persistence_detail,
        )
    if policy.block_persistence_degraded and repository is not None:
        _check(
            checks,
            "persistence-health",
            persistence_status == "READY",
            persistence_detail,
        )

    return SessionReadinessReport(
        policy_enabled=True,
        ready=all(check.passed for check in checks),
        checks=checks,
    )
