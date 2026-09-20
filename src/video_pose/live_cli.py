from __future__ import annotations

import argparse
import json
import time
from typing import Any

from .live_runtime import LiveAnalysisUpdate, build_live_runtime
from .runtime_config import load_analysis_config


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run Video Pose against live four-camera streams"
    )
    parser.add_argument("--config", required=True, help="Live analysis YAML")
    return parser


def _update_payload(update: LiveAnalysisUpdate) -> dict[str, Any]:
    return {
        "timestamp_ms": update.trace.frame_set.reference_timestamp_ms,
        "actions": [
            action.model_dump(mode="json", by_alias=True)
            for action in update.trace.actions
        ],
        "rule_updates": [
            {
                "new_violations": [
                    item.model_dump(mode="json")
                    for item in rule_update.new_violations
                ],
                "changed_steps": [
                    item.model_dump(mode="json")
                    for item in rule_update.changed_steps
                ],
                "score": rule_update.result.score,
                "passed": rule_update.result.passed,
            }
            for rule_update in update.rule_updates
        ],
    }


def main() -> int:
    args = build_parser().parse_args()
    runtime = build_live_runtime(load_analysis_config(args.config))

    def emit(update: LiveAnalysisUpdate) -> None:
        print(
            json.dumps(
                _update_payload(update),
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
        print(
            final.model_dump_json(indent=2),
            flush=True,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
