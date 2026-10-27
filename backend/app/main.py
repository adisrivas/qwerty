"""Application factory.

The snapshot is loaded once at start-up. If it cannot be loaded the app still starts and
data routes return 503.
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from http import HTTPStatus
from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app import __version__
from app.api.routes import router
from app.core.config import Settings, get_settings
from app.core.errors import SnapshotIntegrityError, register_error_handlers
from app.core.logging import configure_logging
from app.data.repository import WindDataRepository

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from starlette.responses import Response
    from starlette.types import Scope

log = logging.getLogger(__name__)


class SpaStaticFiles(StaticFiles):
    """Static files with single-page-app fallback.

    A request for a client-side route such as ``/accuracy`` has no file on disk; serve
    ``index.html`` so the React router can handle it. Requests that look like files
    (they have an extension) still 404, so a missing asset is reported honestly.
    """

    async def get_response(self, path: str, scope: Scope) -> Response:
        """Serve the file, or ``index.html`` for extension-less paths that do not exist."""
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code == HTTPStatus.NOT_FOUND and "." not in path.rsplit("/", 1)[-1]:
                return await super().get_response("index.html", scope)
            raise


def load_repository(settings: Settings) -> WindDataRepository:
    """Load the committed snapshot into memory."""
    repo = WindDataRepository.from_snapshot(settings.snapshot_dir)
    extent = repo.extent()
    log.info(
        "snapshot loaded",
        extra={
            "ctx_issues": extent.issue_count,
            "ctx_actuals": extent.actual_count,
            "ctx_dir": str(settings.snapshot_dir),
        },
    )
    return repo


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the FastAPI application."""
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        try:
            app.state.repository = load_repository(settings)
        except SnapshotIntegrityError:
            log.exception("snapshot could not be loaded; data routes will return 503")
            app.state.repository = None
        yield

    app = FastAPI(
        title=f"{settings.app_name} API",
        version=__version__,
        summary="Day-ahead wind forecast decision support (Elexon WINDFOR vs FUELHH).",
        lifespan=lifespan,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        redoc_url=None,
    )
    register_error_handlers(app)
    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_methods=["GET"],
            allow_headers=["*"],
        )
    app.include_router(router)

    static_dir = os.environ.get("WINDFORECAST_STATIC_DIR")
    if static_dir and Path(static_dir).is_dir():
        app.mount("/", SpaStaticFiles(directory=static_dir, html=True), name="frontend")

    return app


app = create_app()
