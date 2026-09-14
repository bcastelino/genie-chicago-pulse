from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import main as entrypoint
from proxy import ProxySettings


def test_entrypoint_bootstraps_function_root(monkeypatch):
    function_root = Path(entrypoint.__file__).resolve().parent
    monkeypatch.chdir(function_root.parent)
    monkeypatch.setattr(
        sys,
        "path",
        [
            value
            for value in sys.path
            if value and Path(value).resolve() != function_root
        ],
    )
    monkeypatch.delitem(sys.modules, "src", raising=False)
    monkeypatch.delitem(sys.modules, "src.proxy", raising=False)

    spec = importlib.util.spec_from_file_location(
        "appwrite_bootstrap_entrypoint", function_root / "main.py"
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)

    spec.loader.exec_module(module)

    assert sys.path[0] == str(function_root)
    assert module.ProxyGateway.__module__ == "src.proxy"


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
