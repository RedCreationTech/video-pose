from __future__ import annotations

import argparse

from .model_release import (
    build_model_release_manifest,
    load_model_release_manifest,
    verify_model_release_manifest,
    write_model_release_manifest,
)
from .runtime_config import load_analysis_config


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate or verify Video Pose model release manifests"
    )
    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
    )

    generate = subparsers.add_parser("generate")
    generate.add_argument("--config", required=True)
    generate.add_argument("--release-id", required=True)
    generate.add_argument("--output", required=True)

    verify = subparsers.add_parser("verify")
    verify.add_argument("--manifest", required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.command == "generate":
        manifest = build_model_release_manifest(
            load_analysis_config(args.config),
            release_id=args.release_id,
        )
        write_model_release_manifest(
            manifest,
            args.output,
        )
        print(manifest.model_dump_json(indent=2))
        return 0

    manifest = load_model_release_manifest(args.manifest)
    verification = verify_model_release_manifest(manifest)
    print(verification.model_dump_json(indent=2))
    return 0 if verification.passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
