from __future__ import annotations

import argparse
from pathlib import Path

import yaml

from .camera_model import (
    build_perspective_profile,
    load_camera_model_profile,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build 3x4 camera projection matrices from K, R and t"
    )
    parser.add_argument("--input", required=True, help="Camera model YAML")
    parser.add_argument("--output", required=True, help="Perspective YAML")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    profile = build_perspective_profile(load_camera_model_profile(args.input))
    payload = profile.model_dump(mode="json")
    Path(args.output).write_text(
        yaml.safe_dump(payload, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    print(
        f"profile={profile.profile_id} cameras={len(profile.cameras)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
