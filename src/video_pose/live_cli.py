from __future__ import annotations

import argparse
import json
import time

from .live_payload import live_update_payload
from .live_runtime import LiveAnalysisUpdate, build_live_runtime
from .runtime_config import load_analysis_config


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run Video Pose against live four-camera streams"
    )
    parser.add_argument("--config", required=True, help="Live analysis YAML")
    parser.add_argument("--queue-size", type=int, default=2)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    runtime = build_live_runtime(
        load_analysis_config(args.config),
        processing_queue_size=args.queue_size,
    )

    def emit(update: LiveAnalysisUpdate) -> None:
        print(
            json.dumps(
                live_update_payload(update),
                ensure_ascii=False,
            ),
            flush=True,
        )

    runtime.start(emit)
    try:
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        final = runtime.stop()
        print(final.model_dump_json(indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
