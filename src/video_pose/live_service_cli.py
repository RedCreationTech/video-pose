from __future__ import annotations

import argparse

from .live_service import create_managed_live_app
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
        repository = ResilientSessionStore(
            SQLAlchemySessionRepository(args.database_url)
        )

    hub = build_persistent_camera_hub(
        loaded,
        processing_queue_size=args.queue_size,
    )
    controller = PersistentLiveSessionController(
        loaded,
        hub=hub,
        audit_root=args.audit_dir,
        processing_queue_size=args.queue_size,
        repository=repository,
    )
    app = create_managed_live_app(
        controller,
        autostart=args.autostart,
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
