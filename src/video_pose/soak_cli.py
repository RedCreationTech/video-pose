from __future__ import annotations

import argparse
import time
from pathlib import Path

from .live_runtime import build_live_runtime
from .runtime_config import load_analysis_config
from .soak import SoakMonitor, SoakThresholds


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a long-duration Video Pose live stability test"
    )
    parser.add_argument("--config", required=True)
    parser.add_argument("--duration-hours", type=float, default=72.0)
    parser.add_argument("--sample-seconds", type=float, default=60.0)
    parser.add_argument("--queue-size", type=int, default=2)
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
    return parser


def main() -> int:
    args = build_parser().parse_args()
    thresholds = SoakThresholds(
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
    monitor = SoakMonitor(thresholds)
    runtime = build_live_runtime(
        load_analysis_config(args.config),
        processing_queue_size=args.queue_size,
    )

    started = time.monotonic()
    deadline = started + args.duration_hours * 3600.0
    interrupted = False
    runtime.start(lambda _update: None)

    try:
        while time.monotonic() < deadline:
            elapsed = time.monotonic() - started
            monitor.add(elapsed, runtime.health_snapshot())
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            time.sleep(min(args.sample_seconds, remaining))
    except KeyboardInterrupt:
        interrupted = True
    finally:
        runtime.stop()
        elapsed = time.monotonic() - started
        monitor.add(elapsed, runtime.health_snapshot())

    report = monitor.report()
    Path(args.output).write_text(
        report.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
    )
    print(report.model_dump_json(indent=2))
    if interrupted:
        return 130
    return 0 if report.passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
