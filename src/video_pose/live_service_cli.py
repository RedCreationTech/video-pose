from __future__ import annotations

import argparse
import logging
import os

from .auth import AuthManager
from .live_service import create_managed_live_app
from .model_pool import build_persistent_model_pool
from .persistent_camera import build_persistent_camera_hub
from .persistent_session_controller import PersistentLiveSessionController
from .resilient_store import ResilientSessionStore
from .runtime_config import load_analysis_config
from .structured_log import configure_logging, log_event


LOGGER = logging.getLogger("video_pose.service")


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
        "--log-format",
        choices=["json", "text"],
        default=os.getenv("VIDEO_POSE_LOG_FORMAT", "json"),
    )
    parser.add_argument(
        "--log-level",
        default=os.getenv("VIDEO_POSE_LOG_LEVEL", "INFO"),
    )
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
    configure_logging(
        log_format=args.log_format,
        level=args.log_level,
    )
    log_event(
        LOGGER,
        "service_starting",
        config_path=args.config,
        host=args.host,
        port=args.port,
        database_configured=bool(args.database_url),
        auth_enabled=args.auth_enabled,
        reconcile_on_start=args.reconcile_on_start,
    )
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
        repository = ResilientSessionStore(sql_repository)
        if args.reconcile_on_start:
            reconciliation = repository.reconcile(
                args.audit_dir
            )
            log_event(
                LOGGER,
                "startup_reconciliation_completed",
                repaired_count=reconciliation.repaired_count,
                skipped_count=reconciliation.skipped_count,
                failed_count=reconciliation.failed_count,
                incomplete_count=reconciliation.incomplete_count,
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
    log_event(
        LOGGER,
        "service_runtime_constructed",
        capture_backend=loaded.config.live.backend.value,
        timestamp_source=(
            loaded.config.live.native_timestamp_source.value
            if loaded.config.live.backend.value == "gstreamer-native"
            else "arrival"
        ),
    )
    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        log_level=args.log_level.lower(),
        log_config=None,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
