from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from .live_broker import LiveEventBroker
from .live_metrics import render_prometheus
from .session_controller import (
    LiveSessionController,
    SessionStartRequest,
)


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

    _register_runtime_routes(
        app,
        runtime,
        event_broker,
        Response,
        WebSocket,
        WebSocketDisconnect,
        JSONResponse,
    )
    return app


def create_managed_live_app(
    controller: LiveSessionController,
    *,
    broker: LiveEventBroker | None = None,
    autostart: bool = False,
) -> Any:
    try:
        from fastapi import (
            FastAPI,
            HTTPException,
            Response,
            WebSocket,
            WebSocketDisconnect,
        )
        from fastapi.responses import JSONResponse
    except ImportError as exc:
        raise RuntimeError(
            "Managed live service requires the optional 'api' dependencies"
        ) from exc

    event_broker = broker or LiveEventBroker()
    controller.set_event_callback(event_broker.publish)

    @asynccontextmanager
    async def lifespan(_app: Any) -> AsyncIterator[None]:
        if autostart:
            controller.start()
        try:
            yield
        finally:
            current = controller.current()
            if current is not None and current.status == "RUNNING":
                controller.abort(current.session_id)

    app = FastAPI(
        title="Video Pose Managed Live API",
        version="1",
        lifespan=lifespan,
    )
    app.state.controller = controller
    app.state.broker = event_broker

    _register_runtime_routes(
        app,
        controller,
        event_broker,
        Response,
        WebSocket,
        WebSocketDisconnect,
        JSONResponse,
    )

    @app.post("/api/v1/sessions")
    def start_session(request: SessionStartRequest) -> Any:
        try:
            return controller.start(request).model_dump(mode="json")
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.get("/api/v1/sessions/current")
    def current_session() -> Any:
        current = controller.current()
        return (
            current.model_dump(mode="json")
            if current is not None
            else None
        )

    @app.post("/api/v1/sessions/{session_id}/stop")
    def stop_session(session_id: str) -> Any:
        try:
            return controller.stop(session_id).model_dump(mode="json")
        except (RuntimeError, ValueError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/api/v1/sessions/{session_id}/abort")
    def abort_session(session_id: str) -> Any:
        try:
            return controller.abort(session_id).model_dump(mode="json")
        except (RuntimeError, ValueError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    return app


def _register_runtime_routes(
    app: Any,
    provider: Any,
    event_broker: LiveEventBroker,
    Response: Any,
    WebSocket: Any,
    WebSocketDisconnect: Any,
    JSONResponse: Any,
) -> None:
    @app.get("/health/live")
    def health_live() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/health/ready")
    def health_ready() -> Any:
        snapshot = provider.health_snapshot()
        return JSONResponse(
            snapshot.model_dump(mode="json"),
            status_code=200 if snapshot.ready else 503,
        )

    @app.get("/api/v1/runtime/health")
    def runtime_health() -> dict[str, Any]:
        return provider.health_snapshot().model_dump(mode="json")

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
    def metrics() -> Any:
        return Response(
            render_prometheus(provider.health_snapshot()),
            media_type="text/plain; version=0.0.4",
        )

    @app.websocket("/api/v1/realtime")
    async def realtime(websocket: Any) -> None:
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
