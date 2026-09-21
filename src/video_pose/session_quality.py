from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel

from .contracts import Severity, Violation
from .live_health import CameraState, LiveHealthSnapshot
from .realtime_rules import RuleSessionUpdate
from .runtime_config import SessionQualityRuntimeConfig


class SessionQualityUpdate(BaseModel):
    timestamp_ms: int
    rule_update: RuleSessionUpdate


@dataclass(slots=True)
class _ConditionState:
    first_failed_ms: float
    emitted: bool = False


class SessionQualityMonitor:
    """Convert sustained observability failures into rule violations."""

    def __init__(
        self,
        config: SessionQualityRuntimeConfig,
        *,
        camera_ids: list[str],
    ) -> None:
        self.config = config
        self.camera_ids = tuple(camera_ids)
        self._conditions: dict[str, _ConditionState] = {}
        self._incident_counts: dict[str, int] = {}
        self._sync_base_reference: int | None = None
        self._sync_base_miss: int | None = None
        self._last_sync_emitted: int | None = None
        self._processing_base_received: int | None = None
        self._processing_base_dropped: int | None = None
        self._processing_base_errors: int | None = None
        self._evidence_base_submitted: int | None = None
        self._evidence_base_dropped: int | None = None
        self._evidence_base_errors: int | None = None
        self._audit_base_errors: int | None = None

    def observe(
        self,
        snapshot: LiveHealthSnapshot,
        *,
        now_monotonic_ms: float,
    ) -> list[Violation]:
        output: list[Violation] = []
        if self.config.monitor_cameras:
            output.extend(
                self._camera_incidents(
                    snapshot,
                    now_monotonic_ms=now_monotonic_ms,
                )
            )
        if self.config.monitor_sync:
            output.extend(
                self._sync_incidents(
                    snapshot,
                    now_monotonic_ms=now_monotonic_ms,
                )
            )
        if self.config.monitor_processing:
            output.extend(
                self._processing_incidents(
                    snapshot,
                    now_monotonic_ms=now_monotonic_ms,
                )
            )
        if self.config.monitor_evidence:
            output.extend(
                self._evidence_incidents(
                    snapshot,
                    now_monotonic_ms=now_monotonic_ms,
                )
            )
        if self.config.monitor_audit:
            output.extend(
                self._audit_incidents(
                    snapshot,
                    now_monotonic_ms=now_monotonic_ms,
                )
            )
        return output

    def _camera_incidents(
        self,
        snapshot: LiveHealthSnapshot,
        *,
        now_monotonic_ms: float,
    ) -> list[Violation]:
        by_id = {
            camera.camera_id: camera
            for camera in snapshot.cameras
        }
        output: list[Violation] = []
        for camera_id in self.camera_ids:
            camera = by_id.get(camera_id)
            reasons: list[str] = []
            actual: dict[str, Any] = {}
            if camera is None:
                reasons.append("health missing")
                actual["state"] = "MISSING"
            else:
                actual["state"] = camera.state.value
                if camera.state != CameraState.ONLINE:
                    reasons.append(
                        f"state={camera.state.value}"
                    )
                last = camera.last_frame_monotonic_ms
                if last is None:
                    reasons.append("no frame observed")
                else:
                    stale_ms = max(
                        0.0,
                        now_monotonic_ms - last,
                    )
                    actual["stale_ms"] = stale_ms
                    if (
                        stale_ms
                        > self.config.max_camera_staleness_ms
                    ):
                        reasons.append(
                            f"stale_ms={stale_ms:.1f}"
                        )

            key = f"camera:{camera_id}"
            violation = self._condition_violation(
                key,
                failed=bool(reasons),
                now_monotonic_ms=now_monotonic_ms,
                grace_ms=self.config.camera_grace_ms,
                message=(
                    f"camera {camera_id} quality degraded: "
                    + ", ".join(reasons)
                ),
                expected={
                    "state": "ONLINE",
                    "max_stale_ms": (
                        self.config.max_camera_staleness_ms
                    ),
                },
                actual=actual,
            )
            if violation is not None:
                output.append(violation)
        return output

    def _sync_incidents(
        self,
        snapshot: LiveHealthSnapshot,
        *,
        now_monotonic_ms: float,
    ) -> list[Violation]:
        sync = snapshot.sync
        reasons: list[str] = []
        actual: dict[str, Any] = {}
        if sync is None:
            reasons.append("sync health unavailable")
        else:
            if self._sync_base_reference is None:
                self._sync_base_reference = (
                    sync.reference_frames_total
                )
                self._sync_base_miss = sync.miss_total
                self._last_sync_emitted = sync.emitted_total

            base_reference = self._sync_base_reference or 0
            base_miss = self._sync_base_miss or 0
            attempts = max(
                0,
                sync.reference_frames_total - base_reference,
            )
            misses = max(
                0,
                sync.miss_total - base_miss,
            )
            miss_ratio = misses / attempts if attempts else 0.0
            max_drift = max(
                (
                    abs(value)
                    for value
                    in sync.camera_drift_ms_per_minute.values()
                ),
                default=0.0,
            )
            actual.update(
                {
                    "attempts": attempts,
                    "misses": misses,
                    "miss_ratio": miss_ratio,
                    "p99_skew_ms": sync.skew_p99_ms,
                    "max_abs_drift_ms_per_minute": max_drift,
                    "emitted_total": sync.emitted_total,
                }
            )
            if miss_ratio > self.config.max_sync_miss_ratio:
                reasons.append(
                    f"miss_ratio={miss_ratio:.3f}"
                )
            if (
                sync.skew_p99_ms
                > self.config.max_sync_p99_skew_ms
            ):
                reasons.append(
                    f"p99_skew_ms={sync.skew_p99_ms:.3f}"
                )
            if (
                max_drift
                > self.config.max_abs_sync_drift_ms_per_minute
            ):
                reasons.append(
                    f"drift={max_drift:.3f}ms/min"
                )
            if self._last_sync_emitted == sync.emitted_total:
                reasons.append("synchronized frame output stalled")
            else:
                self._last_sync_emitted = sync.emitted_total

        violation = self._condition_violation(
            "sync",
            failed=bool(reasons),
            now_monotonic_ms=now_monotonic_ms,
            grace_ms=self.config.sync_grace_ms,
            message=(
                "multi-camera synchronization quality degraded: "
                + ", ".join(reasons)
            ),
            expected={
                "max_miss_ratio": self.config.max_sync_miss_ratio,
                "max_p99_skew_ms": (
                    self.config.max_sync_p99_skew_ms
                ),
                "max_abs_drift_ms_per_minute": (
                    self.config.max_abs_sync_drift_ms_per_minute
                ),
            },
            actual=actual,
        )
        return [violation] if violation is not None else []

    def _processing_incidents(
        self,
        snapshot: LiveHealthSnapshot,
        *,
        now_monotonic_ms: float,
    ) -> list[Violation]:
        runtime = snapshot.runtime
        if self._processing_base_received is None:
            self._processing_base_received = (
                runtime.frame_sets_received_total
            )
            self._processing_base_dropped = (
                runtime.frame_sets_dropped_total
            )
            self._processing_base_errors = (
                runtime.processing_errors_total
            )

        base_received = self._processing_base_received or 0
        base_dropped = self._processing_base_dropped or 0
        base_errors = self._processing_base_errors or 0
        received = max(
            0,
            runtime.frame_sets_received_total - base_received,
        )
        dropped = max(
            0,
            runtime.frame_sets_dropped_total - base_dropped,
        )
        errors = max(
            0,
            runtime.processing_errors_total - base_errors,
        )
        drop_ratio = dropped / received if received else 0.0
        reasons: list[str] = []
        if errors > self.config.max_processing_error_delta:
            reasons.append(f"errors={errors}")
        if drop_ratio > self.config.max_processing_drop_ratio:
            reasons.append(
                f"drop_ratio={drop_ratio:.3f}"
            )

        violation = self._condition_violation(
            "processing",
            failed=bool(reasons),
            now_monotonic_ms=now_monotonic_ms,
            grace_ms=self.config.processing_grace_ms,
            message=(
                "inference processing quality degraded: "
                + ", ".join(reasons)
            ),
            expected={
                "max_error_delta": (
                    self.config.max_processing_error_delta
                ),
                "max_drop_ratio": (
                    self.config.max_processing_drop_ratio
                ),
            },
            actual={
                "frame_sets_received_delta": received,
                "frame_sets_dropped_delta": dropped,
                "processing_errors_delta": errors,
                "drop_ratio": drop_ratio,
            },
        )
        return [violation] if violation is not None else []

    def _evidence_incidents(
        self,
        snapshot: LiveHealthSnapshot,
        *,
        now_monotonic_ms: float,
    ) -> list[Violation]:
        evidence = snapshot.evidence
        reasons: list[str] = []
        actual: dict[str, Any] = {}
        if evidence is None:
            reasons.append("evidence health unavailable")
        else:
            if self._evidence_base_submitted is None:
                self._evidence_base_submitted = (
                    evidence.submitted_total
                )
                self._evidence_base_dropped = (
                    evidence.dropped_total
                )
                self._evidence_base_errors = (
                    evidence.errors_total
                )

            base_submitted = self._evidence_base_submitted or 0
            base_dropped = self._evidence_base_dropped or 0
            base_errors = self._evidence_base_errors or 0
            submitted = max(
                0,
                evidence.submitted_total - base_submitted,
            )
            dropped = max(
                0,
                evidence.dropped_total - base_dropped,
            )
            errors = max(
                0,
                evidence.errors_total - base_errors,
            )
            drop_ratio = (
                dropped / submitted if submitted else 0.0
            )
            actual.update(
                {
                    "submitted_delta": submitted,
                    "dropped_delta": dropped,
                    "errors_delta": errors,
                    "drop_ratio": drop_ratio,
                    "over_capacity": evidence.over_capacity,
                }
            )
            if errors > self.config.max_evidence_error_delta:
                reasons.append(f"errors={errors}")
            if drop_ratio > self.config.max_evidence_drop_ratio:
                reasons.append(
                    f"drop_ratio={drop_ratio:.3f}"
                )
            if (
                self.config.block_evidence_over_capacity
                and evidence.over_capacity
            ):
                reasons.append("over_capacity=true")

        violation = self._condition_violation(
            "evidence",
            failed=bool(reasons),
            now_monotonic_ms=now_monotonic_ms,
            grace_ms=self.config.evidence_grace_ms,
            message=(
                "evidence capture quality degraded: "
                + ", ".join(reasons)
            ),
            expected={
                "max_error_delta": (
                    self.config.max_evidence_error_delta
                ),
                "max_drop_ratio": (
                    self.config.max_evidence_drop_ratio
                ),
                "over_capacity": False,
            },
            actual=actual,
        )
        return [violation] if violation is not None else []

    def _audit_incidents(
        self,
        snapshot: LiveHealthSnapshot,
        *,
        now_monotonic_ms: float,
    ) -> list[Violation]:
        audit = snapshot.audit
        reasons: list[str] = []
        actual: dict[str, Any] = {}
        if audit is None:
            reasons.append("audit health unavailable")
        else:
            if self._audit_base_errors is None:
                self._audit_base_errors = audit.write_errors_total
            base_errors = self._audit_base_errors or 0
            errors = max(
                0,
                audit.write_errors_total - base_errors,
            )
            actual.update(
                {
                    "status": audit.status,
                    "write_errors_delta": errors,
                    "last_error": audit.last_error,
                }
            )
            if audit.status != "READY":
                reasons.append(f"status={audit.status}")
            if errors > self.config.max_audit_error_delta:
                reasons.append(f"errors={errors}")

        violation = self._condition_violation(
            "audit",
            failed=bool(reasons),
            now_monotonic_ms=now_monotonic_ms,
            grace_ms=self.config.audit_grace_ms,
            message=(
                "immutable audit write quality degraded: "
                + ", ".join(reasons)
            ),
            expected={
                "status": "READY",
                "max_error_delta": (
                    self.config.max_audit_error_delta
                ),
            },
            actual=actual,
        )
        return [violation] if violation is not None else []

    def _condition_violation(
        self,
        key: str,
        *,
        failed: bool,
        now_monotonic_ms: float,
        grace_ms: int,
        message: str,
        expected: dict[str, Any],
        actual: dict[str, Any],
    ) -> Violation | None:
        if not failed:
            self._conditions.pop(key, None)
            return None

        state = self._conditions.get(key)
        if state is None:
            state = _ConditionState(
                first_failed_ms=now_monotonic_ms
            )
            self._conditions[key] = state
            if grace_ms > 0:
                return None
        if state.emitted:
            return None
        if now_monotonic_ms - state.first_failed_ms < grace_ms:
            return None

        state.emitted = True
        count = self._incident_counts.get(key, 0) + 1
        self._incident_counts[key] = count
        safe_key = key.replace(":", "-")
        return Violation(
            rule_id=f"SYSTEM-QUALITY-{safe_key.upper()}",
            step="SYSTEM",
            type="SYSTEM_QUALITY",
            severity=Severity(self.config.severity),
            message=message,
            event_id=f"quality-{safe_key}-{count}",
            confidence=1.0,
            expected=expected,
            actual=actual,
        )
