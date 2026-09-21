from __future__ import annotations

import argparse

from .auth import AuthManager
from .live_service import create_managed_live_app
from .model_pool import build_persistent_model_pool
from .persistence_reconcile import reconcile_audit_root
from .persistent_camera import build_persistent_camera_hub
from .persistent_session_controller import PersistentLiveSessionController
from .resilient_store import ResilientSessionStore
from .runtime_config import load_analysis_config


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run Video Pose managed live HTTP/WebSocket service"
    )
    parser.add_argument("--config", required=True)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--queue-size", type=int, default=2)
    parser.add_argument("--audit-dir", default="output/sessions")
    parser.add_argument("--database-url")
    parser.add_argument("--autostart", action="store_true")
    parser.add_argument(
        "--reconcile-on-start",
        action="store_true",
        help=(
            "Repair completed SQL sessions from immutable audit files "
            "before the API starts."
        ),
    )
    parser.add_argument(
        "--auth-enabled",
        action="store_true",
        help=(
            "Require bearer-token authentication. Token hashes are read from "
            "VIDEO_POSE_AUTH_TOKENS_JSON."
        ),
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        import uvicorn
    except ImportError as exc:
        raise RuntimeError(
            "video-pose-serve requires the optional 'api' dependencies"
        ) from exc

    loaded = load_analysis_config(args.config)
    repository = None
    if args.database_url:
        try:
            from .sql_repository import SQLAlchemySessionRepository
        except ImportError as exc:
            raise RuntimeError(
                "database persistence requires the optional 'db' dependencies"
            ) from exc
        sql_repository = SQLAlchemySessionRepository(
            args.database_url
        )
        if args.reconcile_on_start:
            reconciliation = reconcile_audit_root(
                args.audit_dir,
                sql_repository,
            )
            if reconciliation.failed_count:
                raise RuntimeError(
                    "persistence reconciliation failed: "
                    + "; ".join(
                        item.error or item.session_id
                        for item in reconciliation.sessions
                        if item.action == "FAILED"
                    )
                )
        repository = ResilientSessionStore(sql_repository)

    hub = build_persistent_camera_hub(
        loaded,
        processing_queue_size=args.queue_size,
    )
    model_pool = build_persistent_model_pool(loaded)
    controller = PersistentLiveSessionController(
        loaded,
        hub=hub,
        model_pool=model_pool,
        audit_root=args.audit_dir,
        processing_queue_size=args.queue_size,
        repository=repository,
    )
    auth = AuthManager.from_environment(
        force_enabled=True if args.auth_enabled else None
    )
    app = create_managed_live_app(
        controller,
        autostart=args.autostart,
        auth=auth,
    )
    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        log_level="info",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
