"""Public metadata for the Genie Agent behind Ask ChicagoPulse."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException

from ..deps import get_genie_client
from ..genie.client import GenieClient
from ..models import GenieAgentResponse

logger = logging.getLogger("chicagopulse.api")
router = APIRouter()


@router.get("/genie-agent", response_model=GenieAgentResponse)
def genie_agent_info(
    client: GenieClient = Depends(get_genie_client),
) -> GenieAgentResponse:
    try:
        return client.info()
    except Exception:
        logger.exception("Genie Agent metadata lookup failed")
        raise HTTPException(status_code=502, detail="Unable to load Genie Agent details.")
