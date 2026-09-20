from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .offline_runtime import build_offline_runtime
from .runtime_config import load_analysis_config


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Analyze synchronized multi-view videos with Video Pose"
    )
    parser.add_argument("--config", required=True, help="Offline analysis YAML")
    parser.add_argument(
        "--max-frame-sets",
        type=int,
        default=None,
        help="Limit synchronized frame sets for smoke tests",
    )
    parser.add_argument("--output", help="Write JSON result to this file")
    return parser


def _serialize(actions: list[Any], evaluation: Any | None) -> dict[str, Any]:
    return {
        "actions": [
            action.model_dump(mode="json", by_alias=True) for action in actions
        ],
        "evaluation": (
            evaluation.model_dump(mode="json", by_alias=True)
            if evaluation is not None
            else None
        ),
    }


def main() -> int:
    args = build_parser().parse_args()
    loaded = load_analysis_config(args.config)

    with build_offline_runtime(loaded) as runtime:
        frame_sets = runtime.planner.plan()
        if args.max_frame_sets is not None:
            frame_sets = frame_sets[: args.max_frame_sets]
        actions = runtime.pipeline.process(frame_sets)
        evaluation = runtime.rule_engine.evaluate(actions) if actions else None

    payload = _serialize(actions, evaluation)
    rendered = json.dumps(payload, indent=2, ensure_ascii=False)
    if args.output:
        Path(args.output).write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)

    if evaluation is None:
        return 3
    return 0 if evaluation.passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
