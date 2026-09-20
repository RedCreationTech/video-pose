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
