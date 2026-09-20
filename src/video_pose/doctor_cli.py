from __future__ import annotations

import argparse

from .doctor import build_doctor_report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate Video Pose PoC runtime prerequisites"
    )
    parser.add_argument("--config", required=True, help="Offline analysis YAML")
    parser.add_argument(
        "--skip-cuda",
        action="store_true",
        help="Skip CUDA runtime validation",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    report = build_doctor_report(
        args.config,
        include_cuda=not args.skip_cuda,
    )
    if args.json:
        print(report.model_dump_json(indent=2))
    else:
        for check in report.checks:
            marker = "[OK]" if check.status == "PASS" else f"[{check.status}]"
            print(f"{marker:8} {check.name}: {check.detail}")
        print("READY" if report.passed else "NOT READY")
    return 0 if report.passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
