from __future__ import annotations

import argparse

from .camera_model import (
    load_control_points,
    validate_calibration_health,
)
from .perspective import load_perspective_calibration


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate multi-camera reprojection quality"
    )
    parser.add_argument("--calibration", required=True)
    parser.add_argument("--control-points", required=True)
    parser.add_argument("--max-rmse", type=float, default=5.0)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    profile = load_perspective_calibration(args.calibration)
    points = load_control_points(args.control_points)
    report = validate_calibration_health(
        profile,
        points,
        max_rmse=args.max_rmse,
    )
    print(report.model_dump_json(indent=2))
    return 0 if report.passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
