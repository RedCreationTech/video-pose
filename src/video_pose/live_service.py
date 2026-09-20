from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import Any

from .auth import (
    AuthenticationError,
    AuthManager,
    AuthorizationError,
    Permission,
)
from .live_broker import LiveEventBroker
from .live_metrics import render_prometheus
from .session_controller import SessionStartRequest
from .violation_review import ViolationReviewRequest


def create_live_app(
    runtime: Any,
    *,
    autostart: bool = True,
    broker: LiveEventBroker | None = None,
    auth: AuthManager | None = None,
) -> Any:
    try:
        from fastapi import (
            Depends,
            FastAPI,
            Header,
            HTTPException,
            Response,
            WebSocket,
            WebSocketDisconnect,
        )
        from fastapi.responses import JSONResponse
    except ImportError as exc:
        raise RuntimeError(
            "Live HTTP service requires the optional 'api' dependencies"
        ) from exc

    event_broker = broker or LiveEventBroker()
    auth_manager = auth or AuthManager.disabled()

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
    app.state.auth = auth_manager

    _register_runtime_routes(
        app,
        runtime,
        event_broker,
        auth_manager,
        Depends,
        Header,
        HTTPException,
        Response,
        WebSocket,
        WebSocketDisconnect,
        JSONResponse,
    )
    return app


def create_managed_live_app(
    controller: Any,
    *,
    broker: LiveEventBroker | None = None,
    autostart: bool = False,
    auth: AuthManager | None = None,
) -> Any:
    try:
        from fastapi import (
            Depends,
            FastAPI,
            Header,
            HTTPException,
            Query,
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
    auth_manager = auth or AuthManager.disabled()
    controller.set_event_callback(event_broker.publish)

    @asynccontextmanager
    async def lifespan(_app: Any) -> AsyncIterator[None]:
        start_hub = getattr(controller, "start_hub", None)
        shutdown = getattr(controller, "shutdown", None)
        if callable(start_hub):
            start_hub()
        if autostart:
            controller.start()
        try:
            yield
        finally:
            if callable(shutdown):
                shutdown()
            else:
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
    app.state.auth = auth_manager

    require = _build_http_require(
        auth_manager,
        Depends,
        Header,
        HTTPException,
    )

    _register_runtime_routes(
        app,
        controller,
        event_broker,
        auth_manager,
        Depends,
        Header,
        HTTPException,
        Response,
        WebSocket,
        WebSocketDisconnect,
        JSONResponse,
    )

    @app.get("/api/v1/auth/me")
    def auth_me(
        principal: Any = Depends(require(Permission.RUNTIME_READ)),
    ) -> Any:
        return principal.model_dump(mode="json")

    @app.get("/api/v1/cameras")
    def camera_catalog(
        _principal: Any = Depends(require(Permission.CAMERA_READ)),
    ) -> Any:
        method = getattr(controller, "camera_catalog", None)
        if not callable(method):
            raise HTTPException(
                status_code=501,
                detail="camera catalog is unavailable",
            )
        return method()

    @app.get("/api/v1/cameras/{camera_id}/snapshot.jpg")
    def camera_snapshot(
        camera_id: str,
        quality: int = Query(default=80, ge=1, le=100),
        _principal: Any = Depends(require(Permission.CAMERA_READ)),
    ) -> Any:
        method = getattr(controller, "camera_snapshot", None)
        if not callable(method):
            raise HTTPException(
                status_code=501,
                detail="camera snapshot is unavailable",
            )
        try:
            snapshot = method(camera_id, quality=quality)
        except (KeyError, LookupError) as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return Response(
            content=snapshot.content,
            media_type=snapshot.media_type,
            headers={
                "X-Video-Pose-Timestamp-Ms": str(snapshot.timestamp_ms),
                "Cache-Control": "no-store",
            },
        )

    @app.post("/api/v1/sessions")
    def start_session(
        request: SessionStartRequest,
        _principal: Any = Depends(require(Permission.SESSION_START)),
    ) -> Any:
        try:
            return controller.start(request).model_dump(mode="json")
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.get("/api/v1/sessions/current")
    def current_session(
        _principal: Any = Depends(require(Permission.SESSION_READ)),
    ) -> Any:
        current = controller.current()
        return (
            current.model_dump(mode="json")
            if current is not None
            else None
        )

    @app.get("/api/v1/sessions/current/evaluation")
    def current_evaluation(
        _principal: Any = Depends(require(Permission.SESSION_READ)),
    ) -> Any:
        method = getattr(controller, "current_evaluation", None)
        if not callable(method):
            return None
        return method()

    @app.get("/api/v1/sessions")
    def list_sessions(
        limit: int = Query(default=100, ge=1, le=1000),
        _principal: Any = Depends(require(Permission.SESSION_READ)),
    ) -> Any:
        return controller.list_sessions(limit)

    @app.get("/api/v1/sessions/{session_id}")
    def get_session(
        session_id: str,
        _principal: Any = Depends(require(Permission.SESSION_READ)),
    ) -> Any:
        payload = controller.get_session(session_id)
        if payload is None:
            raise HTTPException(status_code=404, detail="session not found")
        return payload

    @app.get("/api/v1/runtime/persistence")
    def persistence_health(
        _principal: Any = Depends(require(Permission.PERSISTENCE_READ)),
    ) -> dict[str, Any]:
        return controller.persistence_health()

    @app.get("/api/v1/reviews/pending")
    def pending_reviews(
        limit: int = Query(default=100, ge=1, le=1000),
        _principal: Any = Depends(require(Permission.VIOLATION_REVIEW)),
    ) -> Any:
        method = getattr(controller, "list_pending_reviews", None)
        if not callable(method):
            return []
        return method(limit)

    @app.post(
        "/api/v1/sessions/{session_id}/violations/{violation_id}/review"
    )
    def review_violation(
        session_id: str,
        violation_id: int,
        request: ViolationReviewRequest,
        principal: Any = Depends(require(Permission.VIOLATION_REVIEW)),
    ) -> Any:
        method = getattr(controller, "review_violation", None)
        if not callable(method):
            raise HTTPException(
                status_code=501,
                detail="violation review is unavailable",
            )
        try:
            return method(
                session_id,
                violation_id,
                request,
                reviewer=principal.subject,
            )
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @app.post("/api/v1/sessions/{session_id}/stop")
    def stop_session(
        session_id: str,
        _principal: Any = Depends(require(Permission.SESSION_CONTROL)),
    ) -> Any:
        try:
            return controller.stop(session_id).model_dump(mode="json")
        except (RuntimeError, ValueError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/api/v1/sessions/{session_id}/abort")
    def abort_session(
        session_id: str,
        _principal: Any = Depends(require(Permission.SESSION_CONTROL)),
    ) -> Any:
        try:
            return controller.abort(session_id).model_dump(mode="json")
        except (RuntimeError, ValueError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    return app


def _build_http_require(
    auth: AuthManager,
    Depends: Any,
    Header: Any,
    HTTPException: Any,
) -> Callable[[Permission], Any]:
    del Depends

    def build(permission: Permission) -> Any:
        def dependency(
            authorization: str | None = Header(default=None),
        ) -> Any:
            try:
                return auth.authorize_bearer(
                    authorization,
                    permission,
                )
            except AuthenticationError as exc:
                raise HTTPException(
                    status_code=401,
                    detail=str(exc),
                    headers={"WWW-Authenticate": "Bearer"},
                ) from exc
            except AuthorizationError as exc:
                raise HTTPException(
                    status_code=403,
                    detail=str(exc),
                ) from exc

        return dependency

    return build


def _register_runtime_routes(
    app: Any,
    provider: Any,
    event_broker: LiveEventBroker,
    auth: AuthManager,
    Depends: Any,
    Header: Any,
    HTTPException: Any,
    Response: Any,
    WebSocket: Any,
    WebSocketDisconnect: Any,
    JSONResponse: Any,
) -> None:
    require = _build_http_require(
        auth,
        Depends,
        Header,
        HTTPException,
    )

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
    def runtime_health(
        _principal: Any = Depends(require(Permission.RUNTIME_READ)),
    ) -> dict[str, Any]:
        return provider.health_snapshot().model_dump(mode="json")

    @app.get("/api/v1/runtime/latest")
    def runtime_latest(
        _principal: Any = Depends(require(Permission.RUNTIME_READ)),
    ) -> dict[str, Any]:
        latest = event_broker.latest()
        if latest is None:
            return {"sequence": 0, "payload": None}
        return {
            "sequence": latest.sequence,
            "payload": latest.payload,
        }

    @app.get("/metrics")
    def metrics(
        _principal: Any = Depends(require(Permission.METRICS_READ)),
    ) -> Any:
        return Response(
            render_prometheus(provider.health_snapshot()),
            media_type="text/plain; version=0.0.4",
        )

    async def realtime(websocket: Any) -> None:
        try:
            authorization = websocket.headers.get("authorization")
            token = websocket.query_params.get("access_token")
            if authorization:
                principal = auth.authenticate_bearer(authorization)
            else:
                principal = auth.authenticate_token(token)
            auth.require(principal, Permission.REALTIME_READ)
        except AuthenticationError:
            await websocket.close(code=4401)
            return
        except AuthorizationError:
            await websocket.close(code=4403)
            return

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

    realtime.__annotations__["websocket"] = WebSocket
    app.websocket("/api/v1/realtime")(realtime)
