"""Genie Conversation API client.

Uses the Databricks SDK's authenticated API client to call the documented REST
endpoints directly. Working with the raw REST JSON (dicts) keeps us decoupled
from SDK object-shape drift and lets the normalizer stay pure. A mock provider
mirrors the same interface for local dev and tests.
"""

from __future__ import annotations

import logging
from typing import Any, Protocol
from urllib.parse import quote

from ..config import Settings
from ..models import FeedbackRating, GenieAgentResponse, GenieMessage, MessageStatus
from .normalize import has_query_attachment, normalize_message

logger = logging.getLogger("chicagopulse.genie")


class GenieProvider(Protocol):
    """Raw transport for Genie calls. All methods return REST-shaped dicts."""

    def start_conversation(self, content: str) -> dict[str, Any]: ...

    def create_message(self, conversation_id: str, content: str) -> dict[str, Any]: ...

    def get_message(self, conversation_id: str, message_id: str) -> dict[str, Any]: ...

    def get_query_result(
        self, conversation_id: str, message_id: str, attachment_id: str
    ) -> dict[str, Any] | None: ...

    def get_space(self) -> dict[str, Any]: ...

    def send_feedback(
        self, conversation_id: str, message_id: str, rating: str, comment: str | None
    ) -> dict[str, Any]: ...

    def workspace_host(self) -> str | None: ...


class DatabricksGenieProvider:
    """Talks to the real Genie Conversation API via the Databricks SDK."""

    def __init__(self, space_id: str, profile: str | None = None, host: str | None = None):
        from databricks.sdk import WorkspaceClient

        self.space_id = space_id
        kwargs: dict[str, Any] = {}
        if profile:
            kwargs["profile"] = profile
        if host:
            kwargs["host"] = host
        self._w = WorkspaceClient(**kwargs)

    def _do(self, method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        return self._w.api_client.do(method, path, body=body) or {}

    def start_conversation(self, content: str) -> dict[str, Any]:
        resp = self._do(
            "POST",
            f"/api/2.0/genie/spaces/{self.space_id}/start-conversation",
            body={"content": content},
        )
        # start-conversation nests the initial message under "message".
        message = resp.get("message") or {}
        conversation = resp.get("conversation") or {}
        if not message.get("conversation_id"):
            message["conversation_id"] = conversation.get("id") or conversation.get(
                "conversation_id"
            )
        return message

    def create_message(self, conversation_id: str, content: str) -> dict[str, Any]:
        return self._do(
            "POST",
            f"/api/2.0/genie/spaces/{self.space_id}/conversations/{conversation_id}/messages",
            body={"content": content},
        )

    def get_message(self, conversation_id: str, message_id: str) -> dict[str, Any]:
        return self._do(
            "GET",
            f"/api/2.0/genie/spaces/{self.space_id}/conversations/{conversation_id}"
            f"/messages/{message_id}",
        )

    def get_query_result(
        self, conversation_id: str, message_id: str, attachment_id: str
    ) -> dict[str, Any] | None:
        resp = self._do(
            "GET",
            f"/api/2.0/genie/spaces/{self.space_id}/conversations/{conversation_id}"
            f"/messages/{message_id}/attachments/{attachment_id}/query-result",
        )
        return resp.get("statement_response") if resp else None

    def get_space(self) -> dict[str, Any]:
        return self._do("GET", f"/api/2.0/genie/spaces/{self.space_id}")

    def send_feedback(
        self, conversation_id: str, message_id: str, rating: str, comment: str | None
    ) -> dict[str, Any]:
        space_id = quote(self.space_id, safe="")
        conversation = quote(conversation_id, safe="")
        message = quote(message_id, safe="")
        body = {"rating": rating}
        if comment:
            body["comment"] = comment
        return self._do(
            "POST",
            f"/api/2.0/genie/spaces/{space_id}/conversations/{conversation}"
            f"/messages/{message}/feedback",
            body=body,
        )

    def workspace_host(self) -> str | None:
        return getattr(self._w.config, "host", None)


class GenieClient:
    """Orchestrates conversation lifecycle and normalization."""

    def __init__(self, provider: GenieProvider, settings: Settings, space_id: str | None):
        self._provider = provider
        self._settings = settings
        self._space_id = space_id

    def start(self, question: str) -> GenieMessage:
        raw = self._provider.start_conversation(question)
        return self._normalize_with_result(raw)

    def info(self) -> GenieAgentResponse:
        raw = self._provider.get_space()
        space_id = str(raw.get("space_id") or self._space_id or "")
        if not space_id:
            raise RuntimeError("The configured Genie Space did not return an ID.")
        host = (self._provider.workspace_host() or self._settings.databricks_host or "").rstrip("/")
        return GenieAgentResponse(
            space_id=space_id,
            title=str(raw.get("title") or "ChicagoPulse Genie"),
            description=str(raw.get("description") or ""),
            warehouse_id=(str(raw["warehouse_id"]) if raw.get("warehouse_id") else None),
            updated_at=(str(raw["update_time"]) if raw.get("update_time") else None),
            space_url=f"{host}/genie/rooms/{quote(space_id, safe='')}" if host else None,
        )

    def follow_up(self, conversation_id: str, question: str) -> GenieMessage:
        raw = self._provider.create_message(conversation_id, question)
        if not raw.get("conversation_id"):
            raw["conversation_id"] = conversation_id
        return self._normalize_with_result(raw)

    def feedback(
        self,
        conversation_id: str,
        message_id: str,
        rating: FeedbackRating,
        comment: str | None,
    ) -> FeedbackRating:
        self._provider.send_feedback(conversation_id, message_id, rating.value, comment)
        return rating

    def poll(self, conversation_id: str, message_id: str) -> GenieMessage:
        raw = self._provider.get_message(conversation_id, message_id)
        if not raw.get("conversation_id"):
            raw["conversation_id"] = conversation_id
        return self._normalize_with_result(raw)

    def _normalize_with_result(self, raw: dict[str, Any]) -> GenieMessage:
        """Normalize a raw message, fetching query results when appropriate."""
        conversation_id = raw.get("conversation_id") or ""
        message_id = raw.get("id") or raw.get("message_id") or ""
        status = (raw.get("status") or "").upper()

        query_result = None
        if status == "COMPLETED":
            attachment_id, _ = has_query_attachment(raw)
            if attachment_id:
                try:
                    query_result = self._provider.get_query_result(
                        conversation_id, message_id, attachment_id
                    )
                except Exception:  # noqa: BLE001 - never crash the request on result fetch
                    logger.exception("Failed to fetch Genie query result")
                    normalized = normalize_message(
                        raw,
                        space_id=self._space_id,
                        max_rows=self._settings.max_result_rows,
                    )
                    return normalized.model_copy(
                        update={
                            "status": MessageStatus.FAILED,
                            "error": "Result data was unavailable. Please retry.",
                        }
                    )

        return normalize_message(
            raw,
            space_id=self._space_id,
            query_result=query_result,
            max_rows=self._settings.max_result_rows,
        )
