"""FastAPI application entrypoint.

Owns all ``/api/*`` routes and, in production, serves the compiled React SPA
from ``frontend/dist`` with a client-side-routing fallback. API routes always
take precedence over static files.
"""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import get_settings
from .routers import conversations, data_health, genie_agent, health, neighborhoods

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("chicagopulse")

# frontend build output: app/frontend/dist (relative to this file: ../frontend/dist)
_DIST_DIR = Path(__file__).resolve().parent.parent / "frontend" / "dist"


def create_app() -> FastAPI:
    settings = get_settings()  # validates config; raises in misconfigured prod
    app = FastAPI(title="ChicagoPulse API", version="0.1.0")

    api = APIRouter(prefix="/api")
    api.include_router(health.router, tags=["health"])
    api.include_router(conversations.router, tags=["conversations"])
    api.include_router(genie_agent.router, tags=["genie-agent"])
    api.include_router(neighborhoods.router, tags=["neighborhoods"])
    api.include_router(data_health.router, tags=["data-health"])
    app.include_router(api)

    _mount_spa(app)

    logger.info(
        "ChicagoPulse started (env=%s, mock_mode=%s)",
        settings.environment,
        settings.mock_mode,
    )
    return app


def _mount_spa(app: FastAPI) -> None:
    """Serve the built SPA, if present, with a history-API fallback."""
    if not _DIST_DIR.exists():
        logger.warning(
            "SPA build not found at %s. API is available; run `npm run build` to serve the UI.",
            _DIST_DIR,
        )
        return

    assets_dir = _DIST_DIR / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    index_file = _DIST_DIR / "index.html"

    @app.get("/{full_path:path}")
    def spa_fallback(full_path: str):
        # Never shadow the API; unknown /api paths should 404 as JSON.
        if full_path.startswith("api/"):
            return JSONResponse({"error": "Not found"}, status_code=404)
        candidate = _DIST_DIR / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(index_file)


app = create_app()
