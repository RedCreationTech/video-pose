from __future__ import annotations

import argparse

from .fault_scenario import run_fault_scenario


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Replay deterministic Video Pose health-fault scenarios"
        )
    )
    parser.add_argument(
        "--scenario",
        action="append",
        required=True,
        help=(
            "Fault scenario YAML. Repeat --scenario to run multiple files."
        ),
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    passed = True
    for path in args.scenario:
        result = run_fault_scenario(path)
        print(result.model_dump_json(indent=2))
        if not result.matched_expectations:
            passed = False
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
