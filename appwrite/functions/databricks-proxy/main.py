"""Appwrite Function entrypoint for the ChicagoPulse public API gateway."""

from __future__ import annotations

import sys
from functools import lru_cache
from pathlib import Path

import requests
from databricks.sdk import WorkspaceClient

_FUNCTION_ROOT = Path(__file__).resolve().parent
if str(_FUNCTION_ROOT) not in sys.path:
    sys.path.insert(0, str(_FUNCTION_ROOT))

from src.proxy import (  # noqa: E402
    ConfigurationError,
    ProxyGateway,
    ProxySettings,
    unavailable_response,
)


@lru_cache(maxsize=1)
def _gateway() -> ProxyGateway:
    settings = ProxySettings.from_env()
    workspace_client = WorkspaceClient(
        host=settings.databricks_host,
        client_id=settings.databricks_client_id,
        client_secret=settings.databricks_client_secret,
        auth_type="oauth-m2m",
    )
    return ProxyGateway(settings, workspace_client, requests.Session())


def main(context):
    """Handle one Appwrite Function domain request."""
    try:
        gateway = _gateway()
    except ConfigurationError as exc:
        context.error(f"Proxy configuration is invalid: {exc}")
        return unavailable_response(context)
    except Exception:
        context.error("Proxy initialization failed.")
        return unavailable_response(context)
    return gateway.handle(context)
