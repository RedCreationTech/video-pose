from __future__ import annotations

import argparse

from .migration import upgrade_database
from .persistence_reconcile import reconcile_audit_root
from .sql_repository import SQLAlchemySessionRepository


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Repair SQL query-store sessions from immutable audit files"
        )
    )
    parser.add_argument("--audit-dir", required=True)
    parser.add_argument("--database-url", required=True)
    parser.add_argument(
        "--include-incomplete",
        action="store_true",
        help=(
            "Also rebuild Sessions without final.json. "
            "Do not use against an actively running Session."
        ),
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    upgrade_database(args.database_url)
    repository = SQLAlchemySessionRepository(args.database_url)
    report = reconcile_audit_root(
        args.audit_dir,
        repository,
        include_incomplete=args.include_incomplete,
    )
    print(report.model_dump_json(indent=2))
    return 0 if report.failed_count == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
