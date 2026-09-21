from __future__ import annotations

from pydantic import BaseModel, Field

from .live_health import LiveHealthSnapshot


class SoakThresholds(BaseModel):
    min_ready_ratio: float = Field(default=0.99, ge=0.0, le=1.0)
    max_drop_ratio: float = Field(default=0.05, ge=0.0, le=1.0)
    max_processing_errors: int = Field(default=0, ge=0)
    max_camera_read_errors: int = Field(default=100, ge=0)
    max_camera_reconnects: int = Field(default=20, ge=0)
    max_processing_latency_ms: float = Field(default=1000.0, gt=0.0)
    max_processing_p99_ms: float = Field(default=750.0, gt=0.0)
    max_rss_growth_mb: float = Field(default=512.0, ge=0.0)
    max_thread_growth: int = Field(default=16, ge=0)
    max_open_fd_growth: int = Field(default=32, ge=0)
    max_evidence_drop_ratio: float = Field(
        default=0.20,
        ge=0.0,
        le=1.0,
    )
    max_evidence_errors: int = Field(default=0, ge=0)
    fail_on_evidence_over_capacity: bool = True
    max_sync_miss_ratio: float = Field(
        default=0.10,
        ge=0.0,
        le=1.0,
    )
    max_sync_p99_skew_ms: float = Field(default=20.0, ge=0.0)
    min_sync_emitted_total: int = Field(default=1, ge=0)
    max_abs_sync_drift_ms_per_minute: float = Field(
        default=2.0,
        ge=0.0,
    )
    min_storage_free_ratio: float = Field(
        default=0.10,
        ge=0.0,
        le=1.0,
    )
    min_storage_free_gb: float = Field(default=5.0, ge=0.0)
    max_audit_write_errors: int = Field(default=0, ge=0)
    fail_on_audit_degraded: bool = True


class SoakSample(BaseModel):
    elapsed_s: float = Field(ge=0.0)
    health: LiveHealthSnapshot


class SoakReport(BaseModel):
    duration_s: float
    sample_count: int
    ready_ratio: float
    frame_sets_received_total: int
    frame_sets_processed_total: int
    frame_sets_dropped_total: int
    drop_ratio: float
    processing_errors_total: int
    camera_read_errors_total: int
    camera_reconnect_total: int
    max_processing_latency_ms: float
    max_processing_p99_ms: float
    initial_rss_mb: float | None
    max_rss_mb: float
    rss_growth_mb: float
    max_gpu_reserved_mb: float
    initial_thread_count: int
    max_thread_count: int
    thread_growth: int
    initial_open_fds: int | None
    max_open_fds: int | None
    open_fd_growth: int | None
    evidence_drop_ratio: float | None
    evidence_errors_total: int | None
    evidence_over_capacity: bool | None
    sync_miss_ratio: float | None
    sync_p99_skew_ms: float | None
    sync_emitted_total: int | None
    max_abs_sync_drift_ms_per_minute: float | None
    min_storage_free_ratio: float | None
    min_storage_free_bytes: int | None
    audit_write_errors_total: int | None
    audit_degraded: bool | None
    passed: bool
    failures: list[str]


class SoakMonitor:
    """Aggregate sampled live health into a release-gate report."""

    def __init__(self, thresholds: SoakThresholds | None = None) -> None:
        self.thresholds = thresholds or SoakThresholds()
        self.samples: list[SoakSample] = []

    def add(
        self,
        elapsed_s: float,
        snapshot: LiveHealthSnapshot,
    ) -> None:
        self.samples.append(
            SoakSample(
                elapsed_s=elapsed_s,
                health=snapshot,
            )
        )

    def report(self) -> SoakReport:
        if not self.samples:
            raise ValueError("at least one soak sample is required")

        ready_count = sum(
            1 for sample in self.samples if sample.health.ready
        )
        ready_ratio = ready_count / len(self.samples)
        latest = self.samples[-1].health
        runtime = latest.runtime
        received = runtime.frame_sets_received_total
        dropped = runtime.frame_sets_dropped_total
        drop_ratio = dropped / received if received else 0.0

        camera_read_errors = sum(
            camera.read_errors_total for camera in latest.cameras
        )
        camera_reconnects = sum(
            camera.reconnect_total for camera in latest.cameras
        )
        max_latency = max(
            (
                sample.health.runtime.max_processing_latency_ms
                for sample in self.samples
            ),
            default=0.0,
        )
        max_p99 = max(
            (
                sample.health.runtime.processing_latency_p99_ms
                for sample in self.samples
            ),
            default=0.0,
        )
        rss_values = [
            sample.health.runtime.current_rss_mb
            for sample in self.samples
            if sample.health.runtime.current_rss_mb is not None
        ]
        initial_rss = rss_values[0] if rss_values else None
        max_rss = max(rss_values, default=0.0)
        rss_growth = (
            max(0.0, max_rss - initial_rss)
            if initial_rss is not None
            else 0.0
        )
        max_gpu_reserved = max(
            (
                sample.health.runtime.max_gpu_reserved_mb
                for sample in self.samples
            ),
            default=0.0,
        )

        thread_values = [
            sample.health.runtime.current_thread_count
            for sample in self.samples
        ]
        initial_thread_count = (
            thread_values[0] if thread_values else 0
        )
        max_thread_count = max(thread_values, default=0)
        thread_growth = max(
            0,
            max_thread_count - initial_thread_count,
        )

        open_fd_values = [
            sample.health.runtime.current_open_fds
            for sample in self.samples
            if sample.health.runtime.current_open_fds is not None
        ]
        initial_open_fds = (
            open_fd_values[0] if open_fd_values else None
        )
        max_open_fds = (
            max(open_fd_values) if open_fd_values else None
        )
        open_fd_growth = (
            max(0, max_open_fds - initial_open_fds)
            if (
                max_open_fds is not None
                and initial_open_fds is not None
            )
            else None
        )

        sync = latest.sync
        sync_miss_ratio = None
        sync_p99_skew_ms = None
        sync_emitted_total = None
        max_abs_sync_drift = None
        if sync is not None:
            attempts = sync.reference_frames_total
            sync_miss_ratio = (
                sync.miss_total / attempts if attempts else 0.0
            )
            sync_p99_skew_ms = sync.skew_p99_ms
            sync_emitted_total = sync.emitted_total
            max_abs_sync_drift = max(
                (
                    abs(value)
                    for value in sync.camera_drift_ms_per_minute.values()
                ),
                default=0.0,
            )

        evidence = latest.evidence
        evidence_drop_ratio = (
            evidence.drop_ratio if evidence is not None else None
        )
        evidence_errors_total = (
            evidence.errors_total if evidence is not None else None
        )
        evidence_over_capacity = (
            evidence.over_capacity if evidence is not None else None
        )

        storage_values = [
            volume
            for sample in self.samples
            for volume in sample.health.storage
        ]
        min_storage_ratio = (
            min(
                volume.free_ratio
                for volume in storage_values
            )
            if storage_values
            else None
        )
        min_storage_bytes = (
            min(
                volume.free_bytes
                for volume in storage_values
            )
            if storage_values
            else None
        )

        audit = latest.audit
        audit_write_errors_total = (
            audit.write_errors_total if audit is not None else None
        )
        audit_degraded = (
            audit.status != "READY"
            if audit is not None
            else None
        )

        failures: list[str] = []
        thresholds = self.thresholds
        if ready_ratio < thresholds.min_ready_ratio:
            failures.append(
                f"ready_ratio={ready_ratio:.6f} "
                f"< {thresholds.min_ready_ratio:.6f}"
            )
        if drop_ratio > thresholds.max_drop_ratio:
            failures.append(
                f"drop_ratio={drop_ratio:.6f} "
                f"> {thresholds.max_drop_ratio:.6f}"
            )
        if (
            runtime.processing_errors_total
            > thresholds.max_processing_errors
        ):
            failures.append(
                "processing_errors_total="
                f"{runtime.processing_errors_total} "
                f"> {thresholds.max_processing_errors}"
            )
        if camera_read_errors > thresholds.max_camera_read_errors:
            failures.append(
                f"camera_read_errors_total={camera_read_errors} "
                f"> {thresholds.max_camera_read_errors}"
            )
        if camera_reconnects > thresholds.max_camera_reconnects:
            failures.append(
                f"camera_reconnect_total={camera_reconnects} "
                f"> {thresholds.max_camera_reconnects}"
            )
        if max_latency > thresholds.max_processing_latency_ms:
            failures.append(
                f"max_processing_latency_ms={max_latency:.3f} "
                f"> {thresholds.max_processing_latency_ms:.3f}"
            )
        if max_p99 > thresholds.max_processing_p99_ms:
            failures.append(
                f"max_processing_p99_ms={max_p99:.3f} "
                f"> {thresholds.max_processing_p99_ms:.3f}"
            )
        if rss_growth > thresholds.max_rss_growth_mb:
            failures.append(
                f"rss_growth_mb={rss_growth:.3f} "
                f"> {thresholds.max_rss_growth_mb:.3f}"
            )
        if thread_growth > thresholds.max_thread_growth:
            failures.append(
                f"thread_growth={thread_growth} "
                f"> {thresholds.max_thread_growth}"
            )
        if (
            open_fd_growth is not None
            and open_fd_growth > thresholds.max_open_fd_growth
        ):
            failures.append(
                f"open_fd_growth={open_fd_growth} "
                f"> {thresholds.max_open_fd_growth}"
            )
        if sync is not None:
            if (
                sync_miss_ratio is not None
                and sync_miss_ratio > thresholds.max_sync_miss_ratio
            ):
                failures.append(
                    f"sync_miss_ratio={sync_miss_ratio:.6f} "
                    f"> {thresholds.max_sync_miss_ratio:.6f}"
                )
            if (
                sync.skew_p99_ms
                > thresholds.max_sync_p99_skew_ms
            ):
                failures.append(
                    f"sync_p99_skew_ms={sync.skew_p99_ms:.3f} "
                    f"> {thresholds.max_sync_p99_skew_ms:.3f}"
                )
            if sync.emitted_total < thresholds.min_sync_emitted_total:
                failures.append(
                    f"sync_emitted_total={sync.emitted_total} "
                    f"< {thresholds.min_sync_emitted_total}"
                )
            if (
                max_abs_sync_drift is not None
                and max_abs_sync_drift
                > thresholds.max_abs_sync_drift_ms_per_minute
            ):
                failures.append(
                    "max_abs_sync_drift_ms_per_minute="
                    f"{max_abs_sync_drift:.6f} "
                    "> "
                    f"{thresholds.max_abs_sync_drift_ms_per_minute:.6f}"
                )

        if audit is not None:
            if (
                audit.write_errors_total
                > thresholds.max_audit_write_errors
            ):
                failures.append(
                    "audit_write_errors_total="
                    f"{audit.write_errors_total} "
                    f"> {thresholds.max_audit_write_errors}"
                )
            if (
                thresholds.fail_on_audit_degraded
                and audit.status != "READY"
            ):
                failures.append(
                    f"audit_status={audit.status}"
                )

        if min_storage_ratio is not None:
            if (
                min_storage_ratio
                < thresholds.min_storage_free_ratio
            ):
                failures.append(
                    f"min_storage_free_ratio={min_storage_ratio:.6f} "
                    f"< {thresholds.min_storage_free_ratio:.6f}"
                )
            assert min_storage_bytes is not None
            min_free_gb = min_storage_bytes / (1024**3)
            if min_free_gb < thresholds.min_storage_free_gb:
                failures.append(
                    f"min_storage_free_gb={min_free_gb:.3f} "
                    f"< {thresholds.min_storage_free_gb:.3f}"
                )

        if evidence is not None:
            if (
                evidence.drop_ratio
                > thresholds.max_evidence_drop_ratio
            ):
                failures.append(
                    f"evidence_drop_ratio={evidence.drop_ratio:.6f} "
                    f"> {thresholds.max_evidence_drop_ratio:.6f}"
                )
            if (
                evidence.errors_total
                > thresholds.max_evidence_errors
            ):
                failures.append(
                    "evidence_errors_total="
                    f"{evidence.errors_total} "
                    f"> {thresholds.max_evidence_errors}"
                )
            if (
                thresholds.fail_on_evidence_over_capacity
                and evidence.over_capacity
            ):
                failures.append("evidence_over_capacity=true")

        return SoakReport(
            duration_s=self.samples[-1].elapsed_s,
            sample_count=len(self.samples),
            ready_ratio=ready_ratio,
            frame_sets_received_total=received,
            frame_sets_processed_total=runtime.frame_sets_processed_total,
            frame_sets_dropped_total=dropped,
            drop_ratio=drop_ratio,
            processing_errors_total=runtime.processing_errors_total,
            camera_read_errors_total=camera_read_errors,
            camera_reconnect_total=camera_reconnects,
            max_processing_latency_ms=max_latency,
            max_processing_p99_ms=max_p99,
            initial_rss_mb=initial_rss,
            max_rss_mb=max_rss,
            rss_growth_mb=rss_growth,
            max_gpu_reserved_mb=max_gpu_reserved,
            initial_thread_count=initial_thread_count,
            max_thread_count=max_thread_count,
            thread_growth=thread_growth,
            initial_open_fds=initial_open_fds,
            max_open_fds=max_open_fds,
            open_fd_growth=open_fd_growth,
            evidence_drop_ratio=evidence_drop_ratio,
            evidence_errors_total=evidence_errors_total,
            evidence_over_capacity=evidence_over_capacity,
            sync_miss_ratio=sync_miss_ratio,
            sync_p99_skew_ms=sync_p99_skew_ms,
            sync_emitted_total=sync_emitted_total,
            max_abs_sync_drift_ms_per_minute=max_abs_sync_drift,
            min_storage_free_ratio=min_storage_ratio,
            min_storage_free_bytes=min_storage_bytes,
            audit_write_errors_total=audit_write_errors_total,
            audit_degraded=audit_degraded,
            passed=not failures,
            failures=failures,
        )
