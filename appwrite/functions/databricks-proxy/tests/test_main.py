from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import main as entrypoint
from proxy import ProxySettings, WakeSettings


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


def test_gateway_constructs_a_separate_wake_identity(monkeypatch):
    settings = ProxySettings(
        databricks_host="https://dbc-example.cloud.databricks.com",
        databricks_client_id="gateway-client-id",
        databricks_client_secret="gateway-client-secret",
        databricks_app_url="https://chicagopulse-123.aws.databricksapps.com",
        allowed_origins=frozenset({"https://site.appwrite.network"}),
    )
    wake_settings = WakeSettings(
        databricks_host=settings.databricks_host,
        databricks_client_id="wake-client-id",
        databricks_client_secret="wake-client-secret",
        databricks_app_name="chicagopulse",
    )
    workspace_calls = []

    class FakeWorkspaceClient:
        def __init__(self, **kwargs):
            workspace_calls.append(kwargs)

    monkeypatch.setattr(entrypoint.ProxySettings, "from_env", lambda: settings)
    monkeypatch.setattr(
        entrypoint.WakeSettings,
        "from_env",
        lambda databricks_host: wake_settings,
    )
    monkeypatch.setattr(entrypoint, "WorkspaceClient", FakeWorkspaceClient)
    monkeypatch.setattr(entrypoint.requests, "Session", object)
    entrypoint._gateway.cache_clear()

    try:
        gateway = entrypoint._gateway()
    finally:
        entrypoint._gateway.cache_clear()

    assert gateway._workspace_client is not gateway._wake_workspace_client
    assert workspace_calls == [
        {
            "host": settings.databricks_host,
            "client_id": "gateway-client-id",
            "client_secret": "gateway-client-secret",
            "auth_type": "oauth-m2m",
        },
        {
            "host": settings.databricks_host,
            "client_id": "wake-client-id",
            "client_secret": "wake-client-secret",
            "auth_type": "oauth-m2m",
        },
    ]


def test_wake_client_failure_preserves_normal_gateway_initialization(monkeypatch):
    settings = ProxySettings(
        databricks_host="https://dbc-example.cloud.databricks.com",
        databricks_client_id="gateway-client-id",
        databricks_client_secret="gateway-client-secret",
        databricks_app_url="https://chicagopulse-123.aws.databricksapps.com",
        allowed_origins=frozenset({"https://site.appwrite.network"}),
    )
    wake_settings = WakeSettings(
        databricks_host=settings.databricks_host,
        databricks_client_id="wake-client-id",
        databricks_client_secret="wake-client-secret",
        databricks_app_name="chicagopulse",
    )
    normal_workspace = object()
    workspace_calls = []

    def fake_workspace_client(**kwargs):
        workspace_calls.append(kwargs)
        if len(workspace_calls) == 1:
            return normal_workspace
        raise TypeError("sensitive configuration must not be logged")

    monkeypatch.setattr(entrypoint.ProxySettings, "from_env", lambda: settings)
    monkeypatch.setattr(
        entrypoint.WakeSettings,
        "from_env",
        lambda databricks_host: wake_settings,
    )
    monkeypatch.setattr(entrypoint, "WorkspaceClient", fake_workspace_client)
    monkeypatch.setattr(entrypoint.requests, "Session", object)
    entrypoint._gateway.cache_clear()

    try:
        gateway = entrypoint._gateway()
    finally:
        entrypoint._gateway.cache_clear()

    assert gateway._workspace_client is normal_workspace
    assert gateway._wake_workspace_client is None
    assert gateway._wake_initialization_error_type == "TypeError"
    assert workspace_calls[0] == {
        "host": settings.databricks_host,
        "client_id": "gateway-client-id",
        "client_secret": "gateway-client-secret",
        "auth_type": "oauth-m2m",
    }
    assert workspace_calls[1] == {
        "host": settings.databricks_host,
        "client_id": "wake-client-id",
        "client_secret": "wake-client-secret",
        "auth_type": "oauth-m2m",
    }
