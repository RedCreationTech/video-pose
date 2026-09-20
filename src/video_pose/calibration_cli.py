from __future__ import annotations

import argparse
from pathlib import Path

import yaml
from pydantic import BaseModel

from .homography import HomographyCorrespondence, fit_homography


class CalibrationInput(BaseModel):
    camera_id: str
    correspondences: list[HomographyCorrespondence]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Fit a planar image-to-world homography"
    )
    parser.add_argument("--input", required=True, help="Correspondence YAML")
    parser.add_argument("--output", required=True, help="Calibration YAML")
    parser.add_argument(
        "--max-rmse",
        type=float,
        default=30.0,
        help="Return failure if reprojection RMSE exceeds this value",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    input_path = Path(args.input)
    payload = CalibrationInput.model_validate(
        yaml.safe_load(input_path.read_text(encoding="utf-8"))
    )
    result = fit_homography(payload.correspondences)
    output = {
        "camera_id": payload.camera_id,
        "homography": result.homography,
        "reprojection_rmse": result.rmse,
        "point_errors": result.point_errors,
    }
    Path(args.output).write_text(
        yaml.safe_dump(output, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    print(f"camera={payload.camera_id} rmse={result.rmse:.3f}")
    return 0 if result.rmse <= args.max_rmse else 2


if __name__ == "__main__":
    raise SystemExit(main())
