from __future__ import annotations

from typing import Any

from .web_console_assets import APP_JS, INDEX_HTML, STYLE_CSS


def register_web_console(
    app: Any,
    Response: Any,
) -> None:
    common_headers = {
        "Cache-Control": "no-store",
        "X-Content-Type-Options": "nosniff",
        "Referrer-Policy": "no-referrer",
    }

    @app.get("/console", include_in_schema=False)
    @app.get("/console/", include_in_schema=False)
    def console_index() -> Any:
        return Response(
            INDEX_HTML,
            media_type="text/html; charset=utf-8",
            headers={
                **common_headers,
                "Content-Security-Policy": (
                    "default-src 'self'; "
                    "img-src 'self' blob: data:; "
                    "style-src 'self'; "
                    "script-src 'self'; "
                    "connect-src 'self'; "
                    "object-src 'none'; "
                    "base-uri 'none'; "
                    "frame-ancestors 'none'"
                ),
            },
        )

    @app.get("/console/style.css", include_in_schema=False)
    def console_style() -> Any:
        return Response(
            STYLE_CSS,
            media_type="text/css; charset=utf-8",
            headers=common_headers,
        )

    @app.get("/console/app.js", include_in_schema=False)
    def console_script() -> Any:
        return Response(
            APP_JS,
            media_type="application/javascript; charset=utf-8",
            headers=common_headers,
        )
