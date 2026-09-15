from __future__ import annotations

import json
from dataclasses import dataclass
from types import SimpleNamespace

import pytest
import requests

from proxy import ConfigurationError, ProxyGateway, ProxySettings, unavailable_response


@dataclass
class FunctionResponse:
    body: object
    status_code: int
    headers: dict[str, str]


class FakeResponseBuilder:
    def json(self, body, status_code=200, headers=None):
        return FunctionResponse(body, status_code, dict(headers or {}))

    def text(self, body, status_code=200, headers=None):
        return FunctionResponse(body, status_code, dict(headers or {}))


class FakeContext:
    def __init__(self, *, method="GET", path="/api/health", headers=None, body="", query=None):
        self.req = SimpleNamespace(
            method=method,
            path=path,
            headers=headers or {},
            body_text=body,
            query=query or {},
        )
        self.res = FakeResponseBuilder()
        self.errors: list[str] = []
        self.logs: list[str] = []

    def error(self, message):
        self.errors.append(message)

    def log(self, message):
        self.logs.append(message)


class FakeWorkspaceConfig:
    def __init__(self):
        self.calls = 0

    def authenticate(self):
        self.calls += 1
        return {
            "Authorization": f"Bearer current-token-{self.calls}",
            "X-Unsafe-SDK-Header": "do-not-forward",
        }


class FakeWorkspaceClient:
    def __init__(self):
        self.config = FakeWorkspaceConfig()


class FakeUpstreamResponse:
    def __init__(self, body=None, status_code=200):
        self.status_code = status_code
        self.text = "" if body is None else json.dumps(body)


class FakeHttpClient:
    def __init__(self, responses=None, error=None):
        self.responses = list(responses or [FakeUpstreamResponse({"status": "ok"})])
        self.error = error
        self.calls: list[tuple[str, str, dict]] = []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        if self.error:
            raise self.error
        return self.responses.pop(0)


@pytest.fixture
def settings():
    return ProxySettings(
        databricks_host="https://dbc-example.cloud.databricks.com",
        databricks_client_id="client-id",
        databricks_client_secret="client-secret",
        databricks_app_url="https://chicagopulse-123.aws.databricksapps.com",
        allowed_origins=frozenset(
            {"https://site.appwrite.network", "http://localhost:5173"}
        ),
    )


def make_gateway(settings, responses=None, error=None):
    workspace = FakeWorkspaceClient()
    http = FakeHttpClient(responses=responses, error=error)
    return ProxyGateway(settings, workspace, http), workspace, http


def test_allowed_get_route_uses_server_generated_authorization(settings):
    gateway, workspace, http = make_gateway(settings)
    context = FakeContext(
        headers={
            "Origin": "https://site.appwrite.network",
            "Authorization": "Bearer attacker-token",
            "Cookie": "private=value",
        }
    )

    result = gateway.handle(context)

    assert result.status_code == 200
    assert result.headers["Access-Control-Allow-Origin"] == "https://site.appwrite.network"
    method, url, kwargs = http.calls[0]
    assert method == "GET"
    assert url == "https://chicagopulse-123.aws.databricksapps.com/api/health"
    assert kwargs["headers"] == {
        "Accept": "application/json",
        "Authorization": "Bearer current-token-1",
    }
    assert kwargs["verify"] is True
    assert kwargs["allow_redirects"] is False
    assert workspace.config.calls == 1


def test_allowed_post_forwards_json_body_only(settings):
    gateway, _, http = make_gateway(
        settings, [FakeUpstreamResponse({"conversation_id": "abc"})]
    )
    context = FakeContext(
        method="POST",
        path="/api/conversations",
        headers={"Content-Type": "application/json; charset=utf-8"},
        body='{"question":"How is Austin doing?"}',
    )

    result = gateway.handle(context)

    assert result.status_code == 200
    _, _, kwargs = http.calls[0]
    assert kwargs["data"] == '{"question":"How is Austin doing?"}'
    assert kwargs["headers"]["Content-Type"] == "application/json; charset=utf-8"


def test_query_string_is_forwarded(settings):
    gateway, _, http = make_gateway(settings)
    context = FakeContext(
        path="/api/neighborhoods/compare", query={"areas": "1,2"}
    )

    gateway.handle(context)

    assert http.calls[0][1].endswith("/api/neighborhoods/compare?areas=1%2C2")


def test_query_embedded_in_path_is_preserved(settings):
    gateway, _, http = make_gateway(settings)
    gateway.handle(FakeContext(path="/api/neighborhoods/compare?areas=3,4"))

    assert http.calls[0][1].endswith("/api/neighborhoods/compare?areas=3,4")


def test_valid_preflight_returns_no_content_without_upstream_call(settings):
    gateway, workspace, http = make_gateway(settings)
    context = FakeContext(
        method="OPTIONS",
        path="/api/conversations",
        headers={
            "Origin": "https://site.appwrite.network",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    result = gateway.handle(context)

    assert result.status_code == 204
    assert result.headers["Access-Control-Allow-Origin"] == "https://site.appwrite.network"
    assert result.headers["Access-Control-Allow-Headers"] == "Content-Type"
    assert "Access-Control-Allow-Credentials" not in result.headers
    assert http.calls == []
    assert workspace.config.calls == 0


def test_rejected_origin_returns_403_without_cors_header(settings):
    gateway, _, http = make_gateway(settings)
    result = gateway.handle(
        FakeContext(headers={"Origin": "https://attacker.example"})
    )

    assert result.status_code == 403
    assert "Access-Control-Allow-Origin" not in result.headers
    assert result.headers["Vary"] == "Origin"
    assert http.calls == []


def test_originless_diagnostic_request_is_allowed(settings):
    gateway, _, _ = make_gateway(settings)
    result = gateway.handle(FakeContext())

    assert result.status_code == 200
    assert "Access-Control-Allow-Origin" not in result.headers
    assert result.headers["Vary"] == "Origin"


@pytest.mark.parametrize(
    ("method", "path", "status"),
    [
        ("GET", "/api/unknown", 404),
        ("DELETE", "/api/health", 405),
        ("POST", "/api/data-health/pipeline-runs", 403),
        ("GET", "/api/data-health/pipeline-runs/123", 404),
    ],
)
def test_rejected_routes_do_not_reach_upstream(settings, method, path, status):
    gateway, workspace, http = make_gateway(settings)
    result = gateway.handle(FakeContext(method=method, path=path))

    assert result.status_code == status
    assert http.calls == []
    assert workspace.config.calls == 0


def test_upstream_error_status_and_safe_json_are_preserved(settings):
    gateway, _, _ = make_gateway(
        settings, [FakeUpstreamResponse({"detail": "A question is required."}, 422)]
    )

    result = gateway.handle(
        FakeContext(method="POST", path="/api/conversations", body="{}")
    )

    assert result.status_code == 422
    assert result.body == {"detail": "A question is required."}


def test_empty_upstream_response_is_preserved(settings):
    gateway, _, _ = make_gateway(settings, [FakeUpstreamResponse(None, 204)])

    result = gateway.handle(FakeContext())

    assert result.status_code == 204
    assert result.body == ""


def test_authentication_header_is_refreshed_for_each_request(settings):
    gateway, workspace, http = make_gateway(
        settings,
        [FakeUpstreamResponse({"status": "ok"}), FakeUpstreamResponse({"status": "ok"})],
    )

    gateway.handle(FakeContext())
    gateway.handle(FakeContext(path="/api/genie-agent"))

    assert workspace.config.calls == 2
    assert http.calls[0][2]["headers"]["Authorization"] == "Bearer current-token-1"
    assert http.calls[1][2]["headers"]["Authorization"] == "Bearer current-token-2"


@pytest.mark.parametrize(
    ("error", "expected_status"),
    [(requests.Timeout(), 504), (requests.ConnectionError(), 502)],
)
def test_network_failures_are_sanitized(settings, error, expected_status):
    gateway, _, _ = make_gateway(settings, error=error)

    result = gateway.handle(FakeContext())

    assert result.status_code == expected_status
    serialized = json.dumps(result.body)
    assert settings.databricks_client_secret not in serialized
    assert settings.databricks_app_url not in serialized


def test_redirect_and_non_json_responses_are_sanitized(settings):
    redirect = FakeUpstreamResponse({"location": "internal"}, 302)
    invalid = FakeUpstreamResponse()
    invalid.text = "<html>workspace login</html>"
    gateway, _, _ = make_gateway(settings, [redirect, invalid])

    first = gateway.handle(FakeContext())
    second = gateway.handle(FakeContext())

    assert first.status_code == 502
    assert second.status_code == 502
    assert "workspace login" not in json.dumps(second.body)


def test_non_json_response_logs_only_safe_metadata(settings):
    response_text = "<html>Databricks sign in</html>"
    invalid = FakeUpstreamResponse()
    invalid.text = response_text
    invalid.headers = {"content-type": "text/html; charset=utf-8"}
    gateway, _, _ = make_gateway(settings, [invalid])
    context = FakeContext()

    result = gateway.handle(context)

    diagnostic = "\n".join(context.logs)
    assert result.status_code == 502
    assert "status=200" in diagnostic
    assert "content_type='text/html; charset=utf-8'" in diagnostic
    assert f"body_length={len(response_text)}" in diagnostic
    assert response_text not in diagnostic


def test_malformed_upstream_status_is_sanitized(settings):
    malformed = FakeUpstreamResponse({"status": "ok"})
    malformed.status_code = "not-a-status"
    gateway, _, _ = make_gateway(settings, [malformed])

    result = gateway.handle(FakeContext())

    assert result.status_code == 502
    assert result.body == {"error": "The upstream service returned an invalid response."}


def test_error_payload_containing_configuration_is_sanitized(settings):
    gateway, _, _ = make_gateway(
        settings,
        [FakeUpstreamResponse({"detail": f"bad secret {settings.databricks_client_secret}"}, 500)],
    )

    result = gateway.handle(FakeContext())

    assert result.status_code == 500
    assert settings.databricks_client_secret not in json.dumps(result.body)


def valid_env(**overrides):
    env = {
        "DATABRICKS_HOST": "https://dbc-example.cloud.databricks.com",
        "DATABRICKS_CLIENT_ID": "client-id",
        "DATABRICKS_CLIENT_SECRET": "client-secret",
        "DATABRICKS_APP_URL": "https://chicagopulse-123.aws.databricksapps.com",
        "ALLOWED_ORIGINS": "https://site.appwrite.network,http://localhost:5173",
    }
    env.update(overrides)
    return env


def test_settings_default_and_configurable_timeout():
    assert ProxySettings.from_env(valid_env()).upstream_timeout_seconds == 20
    assert (
        ProxySettings.from_env(
            valid_env(UPSTREAM_TIMEOUT_SECONDS="25")
        ).upstream_timeout_seconds
        == 25
    )


@pytest.mark.parametrize("timeout", ["0", "26", "infinite", "nan"])
def test_settings_reject_invalid_timeout(timeout):
    with pytest.raises(ConfigurationError, match="UPSTREAM_TIMEOUT_SECONDS"):
        ProxySettings.from_env(valid_env(UPSTREAM_TIMEOUT_SECONDS=timeout))


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("DATABRICKS_HOST", "http://dbc-example.cloud.databricks.com"),
        ("DATABRICKS_HOST", "https://dbc-example.cloud.databricks.com/api"),
        ("DATABRICKS_APP_URL", "https://example.com"),
        (
            "DATABRICKS_APP_URL",
            "https://chicagopulse-123.aws.databricksapps.com?redirect=example.com",
        ),
        (
            "DATABRICKS_APP_URL",
            "https://chicagopulse-123.aws.databricksapps.com#fragment",
        ),
        (
            "DATABRICKS_APP_URL",
            "https://user:password@chicagopulse-123.aws.databricksapps.com",
        ),
        ("ALLOWED_ORIGINS", "https://*.appwrite.network"),
        ("ALLOWED_ORIGINS", "http://public.example"),
        ("ALLOWED_ORIGINS", "https://site.appwrite.network/"),
        ("ALLOWED_ORIGINS", "https://site.appwrite.network/path"),
    ],
)
def test_settings_reject_unsafe_urls(key, value):
    with pytest.raises(ConfigurationError):
        ProxySettings.from_env(valid_env(**{key: value}))


def test_unavailable_response_contains_no_configuration():
    context = FakeContext()

    result = unavailable_response(context)

    assert result.status_code == 503
    assert result.body == {"error": "Gateway is unavailable."}
