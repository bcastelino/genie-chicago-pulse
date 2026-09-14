"""Strict public gateway from Appwrite Functions to the ChicagoPulse API."""

from __future__ import annotations

import json
import math
import os
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol
from urllib.parse import urlencode, urlsplit

import requests

_DEFAULT_UPSTREAM_TIMEOUT_SECONDS = 20.0
_MAX_UPSTREAM_TIMEOUT_SECONDS = 25.0
_CONNECT_TIMEOUT_SECONDS = 3.05
_DATABRICKS_APPS_SUFFIX = ".databricksapps.com"
_JSON_CONTENT_TYPE = "application/json"


class ConfigurationError(RuntimeError):
    """Raised when the Function's server-side configuration is unsafe."""


def _required(env: Mapping[str, str], name: str) -> str:
    value = env.get(name, "").strip()
    if not value:
        raise ConfigurationError(f"Missing required variable: {name}")
    return value


def _normalize_https_base(value: str, name: str, *, app_url: bool = False) -> str:
    try:
        parsed = urlsplit(value.strip())
        port = parsed.port
    except ValueError as exc:
        raise ConfigurationError(f"{name} is not a valid URL") from exc

    if parsed.scheme.lower() != "https" or not parsed.hostname:
        raise ConfigurationError(f"{name} must be an HTTPS URL")
    if parsed.username or parsed.password:
        raise ConfigurationError(f"{name} must not contain credentials")
    if parsed.query or parsed.fragment:
        raise ConfigurationError(f"{name} must not contain a query string or fragment")
    if parsed.path not in {"", "/"}:
        raise ConfigurationError(f"{name} must not contain a path")
    if port not in {None, 443}:
        raise ConfigurationError(f"{name} must use the default HTTPS port")

    hostname = parsed.hostname.lower()
    if app_url and not hostname.endswith(_DATABRICKS_APPS_SUFFIX):
        raise ConfigurationError(
            f"{name} must use a {_DATABRICKS_APPS_SUFFIX} hostname"
        )
    return f"https://{hostname}"


def _normalize_origin(value: str) -> str:
    if "*" in value:
        raise ConfigurationError("ALLOWED_ORIGINS does not support wildcards")
    try:
        parsed = urlsplit(value.strip())
        _ = parsed.port
    except ValueError as exc:
        raise ConfigurationError("ALLOWED_ORIGINS contains an invalid URL") from exc

    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        raise ConfigurationError("ALLOWED_ORIGINS entries must be HTTP(S) origins")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ConfigurationError("ALLOWED_ORIGINS entries must be origins only")
    if parsed.path:
        raise ConfigurationError("ALLOWED_ORIGINS entries must not contain paths")

    hostname = parsed.hostname.lower()
    if parsed.scheme.lower() == "http" and hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise ConfigurationError("HTTP origins are allowed only for local development")
    return f"{parsed.scheme.lower()}://{parsed.netloc.lower()}"


@dataclass(frozen=True)
class ProxySettings:
    databricks_host: str
    databricks_client_id: str
    databricks_client_secret: str = field(repr=False)
    databricks_app_url: str = ""
    allowed_origins: frozenset[str] = frozenset()
    upstream_timeout_seconds: float = _DEFAULT_UPSTREAM_TIMEOUT_SECONDS

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> ProxySettings:
        source = os.environ if env is None else env
        host = _normalize_https_base(
            _required(source, "DATABRICKS_HOST"), "DATABRICKS_HOST"
        )
        app_url = _normalize_https_base(
            _required(source, "DATABRICKS_APP_URL"),
            "DATABRICKS_APP_URL",
            app_url=True,
        )
        raw_origins = _required(source, "ALLOWED_ORIGINS")
        origins = frozenset(
            _normalize_origin(value)
            for value in raw_origins.split(",")
            if value.strip()
        )
        if not origins:
            raise ConfigurationError("ALLOWED_ORIGINS must contain at least one origin")

        raw_timeout = source.get(
            "UPSTREAM_TIMEOUT_SECONDS", str(_DEFAULT_UPSTREAM_TIMEOUT_SECONDS)
        ).strip()
        try:
            timeout = float(raw_timeout)
        except ValueError as exc:
            raise ConfigurationError("UPSTREAM_TIMEOUT_SECONDS must be numeric") from exc
        if not math.isfinite(timeout) or not 1 <= timeout <= _MAX_UPSTREAM_TIMEOUT_SECONDS:
            raise ConfigurationError("UPSTREAM_TIMEOUT_SECONDS must be between 1 and 25")

        return cls(
            databricks_host=host,
            databricks_client_id=_required(source, "DATABRICKS_CLIENT_ID"),
            databricks_client_secret=_required(source, "DATABRICKS_CLIENT_SECRET"),
            databricks_app_url=app_url,
            allowed_origins=origins,
            upstream_timeout_seconds=timeout,
        )


@dataclass(frozen=True)
class Route:
    method: str
    pattern: re.Pattern[str]


_SEGMENT = r"[A-Za-z0-9][A-Za-z0-9_-]*"
_PUBLIC_ROUTES = (
    Route("GET", re.compile(r"^/api/health$")),
    Route("GET", re.compile(r"^/api/genie-agent$")),
    Route("GET", re.compile(r"^/api/neighborhoods$")),
    Route("GET", re.compile(r"^/api/neighborhoods/geo$")),
    Route("GET", re.compile(r"^/api/neighborhoods/map$")),
    Route("GET", re.compile(r"^/api/neighborhoods/compare$")),
    Route("GET", re.compile(r"^/api/neighborhoods/[0-9]{1,3}/pulse$")),
    Route("GET", re.compile(r"^/api/data-health$")),
    Route(
        "GET",
        re.compile(
            rf"^/api/conversations/{_SEGMENT}/messages/{_SEGMENT}$"
        ),
    ),
    Route("POST", re.compile(r"^/api/conversations$")),
    Route(
        "POST", re.compile(rf"^/api/conversations/{_SEGMENT}/messages$")
    ),
    Route(
        "POST",
        re.compile(
            rf"^/api/conversations/{_SEGMENT}/messages/{_SEGMENT}/feedback$"
        ),
    ),
)
_PIPELINE_TRIGGER_PATH = "/api/data-health/pipeline-runs"
_PIPELINE_STATUS_PATTERN = re.compile(r"^/api/data-health/pipeline-runs/[0-9]+$")


class WorkspaceConfig(Protocol):
    def authenticate(self) -> Mapping[str, str]: ...


class WorkspaceClientLike(Protocol):
    config: WorkspaceConfig


class HttpClient(Protocol):
    def request(self, method: str, url: str, **kwargs: Any) -> Any: ...


def _header(headers: Mapping[str, Any], name: str) -> str | None:
    lowered = name.lower()
    for key, value in headers.items():
        if str(key).lower() == lowered:
            return str(value)
    return None


def _request_path_and_query(req: Any) -> tuple[str, str]:
    raw_path = str(getattr(req, "path", "/") or "/")
    parsed = urlsplit(raw_path)
    query_string = parsed.query

    if not query_string:
        explicit = getattr(req, "query_string", None) or getattr(req, "queryString", None)
        if explicit:
            query_string = str(explicit).lstrip("?")
        else:
            query = getattr(req, "query", None)
            if isinstance(query, Mapping) and query:
                query_string = urlencode(query, doseq=True)
    return parsed.path or "/", query_string


def _request_body(req: Any) -> str:
    body = getattr(req, "body_text", None)
    if body is None:
        body = getattr(req, "bodyText", None)
    if body is None:
        body = getattr(req, "body", "")
    if isinstance(body, bytes):
        return body.decode("utf-8")
    return str(body or "")


def _allowed_methods(path: str) -> set[str]:
    return {route.method for route in _PUBLIC_ROUTES if route.pattern.fullmatch(path)}


def _cors_headers(origin: str | None) -> dict[str, str]:
    if not origin:
        return {"Vary": "Origin"}
    return {
        "Access-Control-Allow-Origin": origin,
        "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type",
        "Access-Control-Max-Age": "600",
        "Vary": "Origin",
    }


def _json_response(
    context: Any,
    payload: Any,
    status_code: int,
    headers: Mapping[str, str] | None = None,
) -> Any:
    return context.res.json(payload, status_code, dict(headers or {}))


def _empty_response(
    context: Any,
    status_code: int,
    headers: Mapping[str, str] | None = None,
) -> Any:
    return context.res.text("", status_code, dict(headers or {}))


def _error_response(
    context: Any,
    message: str,
    status_code: int,
    headers: Mapping[str, str] | None = None,
) -> Any:
    return _json_response(context, {"error": message}, status_code, headers)


def unavailable_response(context: Any) -> Any:
    """Return the controlled response used when cold-start setup fails."""
    return _error_response(
        context, "Gateway is unavailable.", 503, {"Vary": "Origin"}
    )


class ProxyGateway:
    def __init__(
        self,
        settings: ProxySettings,
        workspace_client: WorkspaceClientLike,
        http_client: HttpClient,
    ) -> None:
        self._settings = settings
        self._workspace_client = workspace_client
        self._http_client = http_client

    def handle(self, context: Any) -> Any:
        req = context.req
        method = str(getattr(req, "method", "GET")).upper()
        path, query_string = _request_path_and_query(req)
        request_headers = getattr(req, "headers", {}) or {}
        origin = _header(request_headers, "Origin")

        if origin and origin not in self._settings.allowed_origins:
            return _error_response(
                context, "Origin is not allowed.", 403, {"Vary": "Origin"}
            )
        response_headers = _cors_headers(origin)

        if method == "OPTIONS":
            return self._preflight(context, path, request_headers, response_headers)

        if path == _PIPELINE_TRIGGER_PATH and method == "POST":
            return _error_response(
                context,
                "Administrative operations are not available through the public gateway.",
                403,
                response_headers,
            )
        if _PIPELINE_STATUS_PATTERN.fullmatch(path) and method == "GET":
            return _error_response(context, "Not found.", 404, response_headers)

        allowed_methods = _allowed_methods(path)
        if not allowed_methods:
            return _error_response(context, "Not found.", 404, response_headers)
        if method not in allowed_methods:
            headers = {**response_headers, "Allow": ", ".join(sorted(allowed_methods))}
            return _error_response(context, "Method not allowed.", 405, headers)

        content_type = _header(request_headers, "Content-Type")
        body = _request_body(req) if method == "POST" else ""
        if method == "POST" and content_type and not content_type.lower().startswith(
            _JSON_CONTENT_TYPE
        ):
            return _error_response(
                context, "Only JSON request bodies are supported.", 415, response_headers
            )

        try:
            generated_headers = self._workspace_client.config.authenticate()
            authorization = _header(generated_headers, "Authorization")
            if not authorization or not authorization.lower().startswith("bearer "):
                raise RuntimeError("OAuth provider did not return a Bearer header")
        except Exception:
            context.error("Databricks OAuth authentication failed.")
            return _error_response(
                context, "Unable to authenticate with the upstream service.", 502, response_headers
            )

        upstream_headers = {
            "Accept": _JSON_CONTENT_TYPE,
            "Authorization": authorization,
        }
        if method == "POST":
            upstream_headers["Content-Type"] = content_type or _JSON_CONTENT_TYPE

        upstream_url = f"{self._settings.databricks_app_url}{path}"
        if query_string:
            upstream_url = f"{upstream_url}?{query_string}"

        try:
            upstream = self._http_client.request(
                method,
                upstream_url,
                headers=upstream_headers,
                data=body if method == "POST" else None,
                timeout=(
                    _CONNECT_TIMEOUT_SECONDS,
                    self._settings.upstream_timeout_seconds,
                ),
                allow_redirects=False,
                verify=True,
            )
        except requests.Timeout:
            context.error("Databricks App request timed out.")
            return _error_response(
                context, "The upstream service timed out.", 504, response_headers
            )
        except requests.RequestException:
            context.error("Databricks App network request failed.")
            return _error_response(
                context, "Unable to reach the upstream service.", 502, response_headers
            )
        except Exception:
            context.error("Unexpected Databricks App request failure.")
            return _error_response(
                context, "Unable to reach the upstream service.", 502, response_headers
            )

        try:
            status_code = int(upstream.status_code)
            response_text = str(getattr(upstream, "text", "") or "")
            if not 100 <= status_code <= 599:
                raise ValueError("invalid HTTP status")
        except Exception:
            context.error("Databricks App returned malformed response metadata.")
            return _error_response(
                context,
                "The upstream service returned an invalid response.",
                502,
                response_headers,
            )

        if 300 <= status_code < 400:
            context.error("Databricks App returned an unexpected redirect.")
            return _error_response(
                context, "The upstream service returned an invalid response.", 502, response_headers
            )

        if status_code == 204 or not response_text:
            return _empty_response(context, status_code, response_headers)

        try:
            payload = json.loads(response_text)
        except (TypeError, ValueError):
            context.error("Databricks App returned a non-JSON response.")
            return _error_response(
                context, "The upstream service returned an invalid response.", 502, response_headers
            )

        if status_code >= 400 and self._must_sanitize_error(payload, response_text):
            payload = {"error": "The upstream service rejected the request."}
        return _json_response(context, payload, status_code, response_headers)

    def _preflight(
        self,
        context: Any,
        path: str,
        request_headers: Mapping[str, Any],
        response_headers: Mapping[str, str],
    ) -> Any:
        requested_method = (_header(request_headers, "Access-Control-Request-Method") or "").upper()
        if not _header(request_headers, "Origin") or not requested_method:
            return _error_response(context, "Invalid preflight request.", 400, response_headers)
        if path == _PIPELINE_TRIGGER_PATH and requested_method == "POST":
            return _error_response(
                context,
                "Administrative operations are not available through the public gateway.",
                403,
                response_headers,
            )
        if _PIPELINE_STATUS_PATTERN.fullmatch(path):
            return _error_response(context, "Not found.", 404, response_headers)

        allowed_methods = _allowed_methods(path)
        if not allowed_methods:
            return _error_response(context, "Not found.", 404, response_headers)
        if requested_method not in allowed_methods:
            headers = {**response_headers, "Allow": ", ".join(sorted(allowed_methods))}
            return _error_response(context, "Method not allowed.", 405, headers)
        return _empty_response(context, 204, response_headers)

    def _must_sanitize_error(self, payload: Any, response_text: str) -> bool:
        sensitive_values = (
            self._settings.databricks_client_secret,
            self._settings.databricks_client_id,
            self._settings.databricks_host,
            self._settings.databricks_app_url,
        )
        if any(value and value in response_text for value in sensitive_values):
            return True
        if not isinstance(payload, dict):
            return True
        if "error_code" in payload or "message" in payload:
            return True
        return "detail" not in payload and "error" not in payload
