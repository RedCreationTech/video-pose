from __future__ import annotations

import argparse

from .migration import downgrade_database, upgrade_database


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Manage Video Pose database schema revisions"
    )
    parser.add_argument("--database-url", required=True)
    parser.add_argument(
        "command",
        choices=["upgrade", "downgrade"],
    )
    parser.add_argument(
        "--revision",
        default="-1",
        help="Downgrade revision, default is -1",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.command == "upgrade":
        upgrade_database(args.database_url)
    else:
        downgrade_database(
            args.database_url,
            args.revision,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
