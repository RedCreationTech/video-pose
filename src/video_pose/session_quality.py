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
            self._conditions[key] = _ConditionState(
                first_failed_ms=now_monotonic_ms
            )
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
