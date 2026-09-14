from __future__ import annotations

import main as entrypoint
from proxy import ProxySettings


def test_gateway_reuses_workspace_client_without_caching_authentication(monkeypatch):
    settings = ProxySettings(
        databricks_host="https://dbc-example.cloud.databricks.com",
        databricks_client_id="client-id",
        databricks_client_secret="client-secret",
        databricks_app_url="https://chicagopulse-123.aws.databricksapps.com",
        allowed_origins=frozenset({"https://site.appwrite.network"}),
    )
    workspace_calls = []
    session = object()

    class FakeWorkspaceClient:
        def __init__(self, **kwargs):
            workspace_calls.append(kwargs)

    monkeypatch.setattr(entrypoint.ProxySettings, "from_env", lambda: settings)
    monkeypatch.setattr(entrypoint, "WorkspaceClient", FakeWorkspaceClient)
    monkeypatch.setattr(entrypoint.requests, "Session", lambda: session)
    entrypoint._gateway.cache_clear()

    try:
        first = entrypoint._gateway()
        second = entrypoint._gateway()
    finally:
        entrypoint._gateway.cache_clear()

    assert first is second
    assert workspace_calls == [
        {
            "host": settings.databricks_host,
            "client_id": settings.databricks_client_id,
            "client_secret": settings.databricks_client_secret,
            "auth_type": "oauth-m2m",
        }
    ]
