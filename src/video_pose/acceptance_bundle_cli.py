from __future__ import annotations

import argparse

from .acceptance_bundle import (
    create_acceptance_bundle,
    verify_acceptance_bundle,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Create or verify a Video Pose release acceptance evidence bundle"
        )
    )
    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
    )

    create = subparsers.add_parser("create")
    create.add_argument("--acceptance", required=True)
    create.add_argument("--output", required=True)
    create.add_argument(
        "--extra",
        action="append",
        default=[],
        help=(
            "Optional extra non-secret release evidence, for example "
            "model-release.json. Repeat as needed."
        ),
    )
    create.add_argument(
        "--allow-not-ready",
        action="store_true",
        help=(
            "Allow packaging a quick/non-production report. "
            "The manifest retains production_ready=false."
        ),
    )

    verify = subparsers.add_parser("verify")
    verify.add_argument("--bundle", required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.command == "create":
        result = create_acceptance_bundle(
            acceptance_report_path=args.acceptance,
            output_path=args.output,
            extra_paths=args.extra,
            allow_not_ready=args.allow_not_ready,
        )
        print(result.model_dump_json(indent=2))
        return 0

    result = verify_acceptance_bundle(args.bundle)
    print(result.model_dump_json(indent=2))
    return 0 if result.passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
