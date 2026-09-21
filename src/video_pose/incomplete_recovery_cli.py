from __future__ import annotations

import argparse

from .incomplete_recovery import (
    IncompleteRecoveryRequest,
    list_incomplete_audit_sessions,
    recover_incomplete_audit_session,
)
from .migration import upgrade_database
from .persistence_reconcile import reconcile_audit_root
from .sql_repository import SQLAlchemySessionRepository


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Recover stale incomplete Audit sessions as ABORTED"
        )
    )
    parser.add_argument("--audit-dir", required=True)
    parser.add_argument("--session-id")
    parser.add_argument("--reason", required=True)
    parser.add_argument(
        "--recovered-by",
        default="operator-cli",
    )
    parser.add_argument("--database-url")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    sessions = list_incomplete_audit_sessions(args.audit_dir)
    selected = [
        item
        for item in sessions
        if args.session_id is None
        or item.session_id == args.session_id
    ]
    if args.session_id is not None and not selected:
        raise RuntimeError(
            f"incomplete session not found: {args.session_id}"
        )

    request = IncompleteRecoveryRequest(reason=args.reason)
    for item in selected:
        result = recover_incomplete_audit_session(
            f"{args.audit_dir}/{item.session_id}",
            request,
            recovered_by=args.recovered_by,
        )
        print(result.model_dump_json())

    if args.database_url:
        upgrade_database(args.database_url)
        repository = SQLAlchemySessionRepository(
            args.database_url
        )
        report = reconcile_audit_root(
            args.audit_dir,
            repository,
        )
        print(report.model_dump_json(indent=2))
        if report.failed_count or report.incomplete_count:
            return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
