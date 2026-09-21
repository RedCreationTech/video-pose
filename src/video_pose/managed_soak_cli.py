from __future__ import annotations

import argparse
import time
import uuid
from pathlib import Path

from .managed_soak import ManagedSoakMonitor, ManagedSoakThresholds
from .model_pool import build_persistent_model_pool
from .persistent_camera import build_persistent_camera_hub
from .persistent_session_controller import PersistentLiveSessionController
from .runtime_config import load_analysis_config
from .session_controller import SessionStartRequest
from .soak import SoakThresholds


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run production-shaped Video Pose soak with persistent cameras, "
            "persistent models and repeated session rotation"
        )
    )
    parser.add_argument("--config", required=True)
    parser.add_argument("--duration-hours", type=float, default=72.0)
    parser.add_argument("--sample-seconds", type=float, default=60.0)
    parser.add_argument("--rotation-seconds", type=float, default=3600.0)
    parser.add_argument("--warmup-seconds", type=float, default=30.0)
    parser.add_argument("--queue-size", type=int, default=2)
    parser.add_argument("--audit-dir", default="output/managed-soak")
    parser.add_argument("--output", required=True)

    parser.add_argument("--min-ready-ratio", type=float, default=0.99)
    parser.add_argument("--max-drop-ratio", type=float, default=0.05)
    parser.add_argument("--max-processing-errors", type=int, default=0)
    parser.add_argument("--max-camera-read-errors", type=int, default=100)
    parser.add_argument("--max-camera-reconnects", type=int, default=20)
    parser.add_argument(
        "--max-processing-latency-ms",
        type=float,
        default=1000.0,
    )
    parser.add_argument(
        "--max-processing-p99-ms",
        type=float,
        default=750.0,
    )
    parser.add_argument(
        "--max-rss-growth-mb",
        type=float,
        default=512.0,
    )
    parser.add_argument(
        "--max-thread-growth",
        type=int,
        default=16,
    )
    parser.add_argument(
        "--max-open-fd-growth",
        type=int,
        default=32,
    )
    parser.add_argument(
        "--max-evidence-drop-ratio",
        type=float,
        default=0.20,
    )
    parser.add_argument(
        "--max-evidence-errors",
        type=int,
        default=0,
    )
    parser.add_argument(
        "--allow-evidence-over-capacity",
        action="store_true",
    )
    parser.add_argument(
        "--max-sync-miss-ratio",
        type=float,
        default=0.10,
    )
    parser.add_argument(
        "--max-sync-p99-skew-ms",
        type=float,
        default=20.0,
    )
    parser.add_argument(
        "--min-sync-emitted-total",
        type=int,
        default=1,
    )
    parser.add_argument(
        "--max-abs-sync-drift-ms-per-minute",
        type=float,
        default=2.0,
    )
    parser.add_argument(
        "--min-storage-free-ratio",
        type=float,
        default=0.10,
    )
    parser.add_argument(
        "--min-storage-free-gb",
        type=float,
        default=5.0,
    )
    parser.add_argument(
        "--max-audit-write-errors",
        type=int,
        default=0,
    )
    parser.add_argument(
        "--allow-audit-degraded",
        action="store_true",
    )
    parser.add_argument(
        "--max-model-warmup-latency-ms",
        type=float,
        default=15000.0,
    )

    parser.add_argument(
        "--max-session-start-errors",
        type=int,
        default=0,
    )
    parser.add_argument(
        "--max-session-stop-errors",
        type=int,
        default=0,
    )
    parser.add_argument(
        "--max-session-start-latency-ms",
        type=float,
        default=5000.0,
    )
    parser.add_argument(
        "--max-session-stop-latency-ms",
        type=float,
        default=5000.0,
    )
    parser.add_argument(
        "--min-completed-sessions",
        type=int,
        default=1,
    )
    return parser


def _health_thresholds(args: argparse.Namespace) -> SoakThresholds:
    return SoakThresholds(
        min_ready_ratio=args.min_ready_ratio,
        max_drop_ratio=args.max_drop_ratio,
        max_processing_errors=args.max_processing_errors,
        max_camera_read_errors=args.max_camera_read_errors,
        max_camera_reconnects=args.max_camera_reconnects,
        max_processing_latency_ms=args.max_processing_latency_ms,
        max_processing_p99_ms=args.max_processing_p99_ms,
        max_rss_growth_mb=args.max_rss_growth_mb,
        max_thread_growth=args.max_thread_growth,
        max_open_fd_growth=args.max_open_fd_growth,
        max_evidence_drop_ratio=args.max_evidence_drop_ratio,
        max_evidence_errors=args.max_evidence_errors,
        fail_on_evidence_over_capacity=(
            not args.allow_evidence_over_capacity
        ),
        max_sync_miss_ratio=args.max_sync_miss_ratio,
        max_sync_p99_skew_ms=args.max_sync_p99_skew_ms,
        min_sync_emitted_total=args.min_sync_emitted_total,
        max_abs_sync_drift_ms_per_minute=(
            args.max_abs_sync_drift_ms_per_minute
        ),
        min_storage_free_ratio=args.min_storage_free_ratio,
        min_storage_free_gb=args.min_storage_free_gb,
        max_audit_write_errors=args.max_audit_write_errors,
        fail_on_audit_degraded=(
            not args.allow_audit_degraded
        ),
        max_model_warmup_latency_ms=(
            args.max_model_warmup_latency_ms
        ),
    )


def _managed_thresholds(
    args: argparse.Namespace,
) -> ManagedSoakThresholds:
    return ManagedSoakThresholds(
        max_session_start_errors=args.max_session_start_errors,
        max_session_stop_errors=args.max_session_stop_errors,
        max_session_start_latency_ms=(
            args.max_session_start_latency_ms
        ),
        max_session_stop_latency_ms=(
            args.max_session_stop_latency_ms
        ),
        min_completed_sessions=args.min_completed_sessions,
    )


def _wait_for_ready(
    controller: PersistentLiveSessionController,
    warmup_s: float,
) -> None:
    deadline = time.monotonic() + max(0.0, warmup_s)
    while time.monotonic() < deadline:
        readiness = controller.readiness()
        if (
            readiness.ready
            if readiness.policy_enabled
            else controller.health_snapshot().ready
        ):
            return
        remaining = deadline - time.monotonic()
        time.sleep(min(1.0, max(0.0, remaining)))


def _start_session(
    controller: PersistentLiveSessionController,
    monitor: ManagedSoakMonitor,
) -> str | None:
    started = time.perf_counter()
    try:
        state = controller.start(
            SessionStartRequest(
                session_id=f"soak-{uuid.uuid4()}",
                operator_id="managed-soak",
            )
        )
    except Exception:
        monitor.record_session_start(
            (time.perf_counter() - started) * 1000.0,
            success=False,
        )
        return None

    monitor.record_session_start(
        (time.perf_counter() - started) * 1000.0,
        success=True,
    )
    return state.session_id


def _stop_session(
    controller: PersistentLiveSessionController,
    monitor: ManagedSoakMonitor,
    session_id: str,
) -> bool:
    started = time.perf_counter()
    try:
        controller.stop(session_id)
    except Exception:
        monitor.record_session_stop(
            (time.perf_counter() - started) * 1000.0,
            success=False,
        )
        return False

    monitor.record_session_stop(
        (time.perf_counter() - started) * 1000.0,
        success=True,
    )
    return True


def main() -> int:
    args = build_parser().parse_args()
    loaded = load_analysis_config(args.config)
    hub = build_persistent_camera_hub(
        loaded,
        processing_queue_size=args.queue_size,
    )
    model_pool = build_persistent_model_pool(loaded)
    controller = PersistentLiveSessionController(
        loaded,
        hub=hub,
        model_pool=model_pool,
        audit_root=args.audit_dir,
        processing_queue_size=args.queue_size,
    )
    monitor = ManagedSoakMonitor(
        health_thresholds=_health_thresholds(args),
        managed_thresholds=_managed_thresholds(args),
    )

    run_started = time.monotonic()
    deadline = run_started + args.duration_hours * 3600.0
    active_session: str | None = None
    interrupted = False
    fatal = False

    try:
        try:
            controller.start_hub()
            monitor.record_hub_start(success=True)
        except Exception:
            monitor.record_hub_start(success=False)
            fatal = True

        monitor.record_model_pool_loaded(model_pool.loaded)
        if not fatal:
            _wait_for_ready(controller, args.warmup_seconds)
            monitor.add_health(
                time.monotonic() - run_started,
                controller.health_snapshot(),
            )
            active_session = _start_session(controller, monitor)
            if active_session is None:
                fatal = True

        next_rotation = (
            time.monotonic() + args.rotation_seconds
            if active_session is not None
            else float("inf")
        )

        while not fatal and time.monotonic() < deadline:
            now = time.monotonic()
            monitor.add_health(
                now - run_started,
                controller.health_snapshot(),
            )

            if now >= next_rotation and active_session is not None:
                if not _stop_session(
                    controller,
                    monitor,
                    active_session,
                ):
                    fatal = True
                    break
                active_session = _start_session(controller, monitor)
                if active_session is None:
                    fatal = True
                    break
                next_rotation = (
                    time.monotonic() + args.rotation_seconds
                )

            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            time.sleep(min(args.sample_seconds, remaining))

    except KeyboardInterrupt:
        interrupted = True
    finally:
        if active_session is not None:
            _stop_session(controller, monitor, active_session)
        if not monitor.health.samples:
            monitor.add_health(
                time.monotonic() - run_started,
                controller.health_snapshot(),
            )
        controller.shutdown()

    report = monitor.report()
    Path(args.output).write_text(
        report.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
    )
    print(report.model_dump_json(indent=2))

    if interrupted:
        return 130
    return 0 if report.passed and not fatal else 2


if __name__ == "__main__":
    raise SystemExit(main())
