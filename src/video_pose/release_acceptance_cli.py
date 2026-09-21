from __future__ import annotations

import argparse
from pathlib import Path

from .release_acceptance import (
    ReleaseAcceptanceThresholds,
    discover_fault_scenarios,
    run_release_acceptance,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Build a Video Pose release acceptance report from "
            "Doctor, Golden Replay, Fault Matrix and Managed Soak evidence"
        )
    )
    parser.add_argument("--config", required=True)
    parser.add_argument(
        "--golden-dataset",
        default="datasets/golden-v1/manifest.yaml",
    )
    parser.add_argument(
        "--fault-dir",
        default="fixtures/faults",
    )
    parser.add_argument("--soak-report")
    parser.add_argument("--output", required=True)
    parser.add_argument(
        "--quick",
        action="store_true",
        help=(
            "Allow exit success when fast checks pass without a "
            "72h soak report. production_ready remains false."
        ),
    )
    parser.add_argument(
        "--min-action-f1",
        type=float,
        default=0.90,
    )
    parser.add_argument(
        "--min-violation-f1",
        type=float,
        default=0.90,
    )
    parser.add_argument(
        "--min-session-accuracy",
        type=float,
        default=0.95,
    )
    parser.add_argument(
        "--min-soak-hours",
        type=float,
        default=72.0,
    )
    parser.add_argument(
        "--min-soak-completed-sessions",
        type=int,
        default=2,
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    faults = discover_fault_scenarios(args.fault_dir)
    report = run_release_acceptance(
        config_path=args.config,
        golden_dataset=args.golden_dataset,
        fault_scenarios=faults,
        soak_report_path=args.soak_report,
        quick=args.quick,
        thresholds=ReleaseAcceptanceThresholds(
            min_action_f1=args.min_action_f1,
            min_violation_f1=args.min_violation_f1,
            min_session_accuracy=args.min_session_accuracy,
            min_soak_hours=args.min_soak_hours,
            min_soak_completed_sessions=(
                args.min_soak_completed_sessions
            ),
        ),
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        report.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
    )
    print(report.model_dump_json(indent=2))

    if args.quick:
        return 0 if report.quick_checks_passed else 2
    return 0 if report.production_ready else 2


if __name__ == "__main__":
    raise SystemExit(main())
