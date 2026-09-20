from __future__ import annotations

import argparse

from .live_runtime import build_live_runtime
from .live_service import create_live_app
from .runtime_config import load_analysis_config


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run Video Pose live HTTP/WebSocket service"
    )
    parser.add_argument("--config", required=True)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--queue-size", type=int, default=2)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        import uvicorn
    except ImportError as exc:
        raise RuntimeError(
            "video-pose-serve requires the optional 'api' dependencies"
        ) from exc

    runtime = build_live_runtime(
        load_analysis_config(args.config),
        processing_queue_size=args.queue_size,
    )
    app = create_live_app(runtime)
    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        log_level="info",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
