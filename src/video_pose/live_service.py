from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from .live_broker import LiveEventBroker
from .live_metrics import render_prometheus


def create_live_app(
    runtime: Any,
    *,
    autostart: bool = True,
    broker: LiveEventBroker | None = None,
) -> Any:
    try:
        from fastapi import FastAPI, Response, WebSocket, WebSocketDisconnect
        from fastapi.responses import JSONResponse
    except ImportError as exc:
        raise RuntimeError(
            "Live HTTP service requires the optional 'api' dependencies"
        ) from exc

    event_broker = broker or LiveEventBroker()

    @asynccontextmanager
    async def lifespan(_app: Any) -> AsyncIterator[None]:
        if autostart:
            runtime.start(event_broker.publish)
        try:
            yield
        finally:
            if autostart:
                runtime.stop()

    app = FastAPI(
        title="Video Pose Live API",
        version="1",
        lifespan=lifespan,
    )
    app.state.runtime = runtime
    app.state.broker = event_broker

    @app.get("/health/live")
    def health_live() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/health/ready")
    def health_ready() -> Any:
        snapshot = runtime.health_snapshot()
        payload = snapshot.model_dump(mode="json")
        return JSONResponse(
            payload,
            status_code=200 if snapshot.ready else 503,
        )

    @app.get("/api/v1/runtime/health")
    def runtime_health() -> dict[str, Any]:
        return runtime.health_snapshot().model_dump(mode="json")

    @app.get("/api/v1/runtime/latest")
    def runtime_latest() -> dict[str, Any]:
        latest = event_broker.latest()
        if latest is None:
            return {"sequence": 0, "payload": None}
        return {
            "sequence": latest.sequence,
            "payload": latest.payload,
        }

    @app.get("/metrics")
    def metrics() -> Response:
        return Response(
            render_prometheus(runtime.health_snapshot()),
            media_type="text/plain; version=0.0.4",
        )

    @app.websocket("/api/v1/realtime")
    async def realtime(websocket: WebSocket) -> None:
        await websocket.accept()
        sequence = 0
        try:
            latest = event_broker.latest()
            if latest is not None:
                await websocket.send_json(
                    {
                        "type": "runtime.update",
                        "sequence": latest.sequence,
                        "payload": latest.payload,
                    }
                )
                sequence = latest.sequence

            while True:
                envelope = await asyncio.to_thread(
                    event_broker.wait_next,
                    sequence,
                    timeout_s=5.0,
                )
                if envelope is None:
                    await websocket.send_json(
                        {
                            "type": "heartbeat",
                            "sequence": sequence,
                        }
                    )
                    continue
                await websocket.send_json(
                    {
                        "type": "runtime.update",
                        "sequence": envelope.sequence,
                        "payload": envelope.payload,
                    }
                )
                sequence = envelope.sequence
        except WebSocketDisconnect:
            return

    return app
