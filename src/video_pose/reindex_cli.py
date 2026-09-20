from __future__ import annotations

import argparse

from .migration import upgrade_database
from .reindex import reindex_audit_root
from .sql_repository import SQLAlchemySessionRepository


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Rebuild query database from immutable session audit files"
    )
    parser.add_argument("--audit-dir", required=True)
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--session-id")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    upgrade_database(args.database_url)
    repository = SQLAlchemySessionRepository(args.database_url)
    results = reindex_audit_root(
        args.audit_dir,
        repository,
        session_id=args.session_id,
    )
    for result in results:
        print(result.model_dump_json())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
