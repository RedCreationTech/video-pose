from __future__ import annotations

import argparse
import getpass

from .auth import hash_token


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Hash a Video Pose bearer token for production configuration"
    )
    parser.add_argument(
        "--token",
        help="Token to hash. Omit to read securely from the terminal.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    token = args.token or getpass.getpass("Video Pose token: ")
    print(hash_token(token))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
