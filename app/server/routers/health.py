"""Health endpoint."""

from __future__ import annotations

from fastapi import APIRouter

from .. import __version__
from ..deps import current_settings
from ..models import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    settings = current_settings()
    return HealthResponse(
        status="ok",
        mock_mode=settings.mock_mode,
        environment=settings.environment,
        version=__version__,
    )
