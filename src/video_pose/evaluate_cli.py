from __future__ import annotations

import argparse

from .golden import evaluate_golden_dataset


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Evaluate Video Pose results against a Golden Replay dataset"
    )
    parser.add_argument("--dataset", required=True, help="Golden dataset YAML")
    parser.add_argument(
        "--min-action-f1",
        type=float,
        default=0.0,
    )
    parser.add_argument(
        "--min-violation-f1",
        type=float,
        default=0.0,
    )
    parser.add_argument(
        "--min-session-accuracy",
        type=float,
        default=0.0,
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    report = evaluate_golden_dataset(args.dataset)
    print(report.model_dump_json(indent=2))
    passed = (
        report.actions.f1 >= args.min_action_f1
        and report.violations.f1 >= args.min_violation_f1
        and report.session_pass_accuracy >= args.min_session_accuracy
    )
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
