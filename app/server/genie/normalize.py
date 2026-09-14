"""Normalize raw Genie Conversation API responses into app contracts.

This module is intentionally provider-shaped-input / app-shaped-output and has
no I/O, so it is fully unit-testable with plain dicts. Both the Databricks SDK
objects (via ``.as_dict()``) and raw REST JSON reduce to the same dict shape.
"""

from __future__ import annotations

from typing import Any

from ..models import (
    Column,
    GenieMessage,
    MessageStatus,
    Provenance,
    QueryResult,
)

# Raw Genie statuses that mean "still working".
_IN_PROGRESS_STATES = {
    "SUBMITTED",
    "IN_PROGRESS",
    "FETCHING_METADATA",
    "FILTERING_CONTEXT",
    "ASKING_AI",
    "PENDING_WAREHOUSE",
    "EXECUTING_QUERY",
}
_ANSWER_PURPOSES = {"TEXT_ATTACHMENT_PURPOSE_ANSWER", None, ""}
_FOLLOW_UP_PURPOSE = "FOLLOW_UP_QUESTION"


def _get(obj: Any, key: str, default: Any = None) -> Any:
    """Read ``key`` from a dict or an attribute-style object."""
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _as_dict(obj: Any) -> Any:
    if obj is None or isinstance(obj, dict | list | str | int | float | bool):
        return obj
    if hasattr(obj, "as_dict"):
        return obj.as_dict()
    return obj


def normalize_query_result(
    statement_response: Any, max_rows: int
) -> QueryResult | None:
    """Normalize a SQL Statement Execution response into a ``QueryResult``."""
    sr = _as_dict(statement_response)
    if not sr:
        return None

    manifest = _get(sr, "manifest") or {}
    schema = _get(manifest, "schema") or {}
    raw_columns = _get(schema, "columns") or []
    columns = [
        Column(
            name=str(_get(c, "name", "")),
            type=str(_get(c, "type_text") or _get(c, "type_name") or "string"),
        )
        for c in raw_columns
    ]

    result = _get(sr, "result") or {}
    data_array = _get(result, "data_array") or []
    rows = [list(r) for r in data_array]
    truncated = bool(_get(manifest, "truncated") or _get(result, "truncated") or False)
    if len(rows) > max_rows:
        rows = rows[:max_rows]
        truncated = True

    total = _get(manifest, "total_row_count")
    row_count = int(total) if total is not None else len(rows)

    return QueryResult(
        columns=columns,
        rows=rows,
        row_count=row_count,
        truncated=truncated,
    )


def _map_status(raw_status: str | None, result: QueryResult | None) -> MessageStatus:
    status = (raw_status or "").upper()
    if status in _IN_PROGRESS_STATES:
        return MessageStatus.IN_PROGRESS
    if status == "FAILED":
        return MessageStatus.FAILED
    if status == "CANCELLED":
        return MessageStatus.CANCELLED
    if status == "QUERY_RESULT_EXPIRED":
        return MessageStatus.EXPIRED
    if status == "COMPLETED":
        # A completed message whose query returned zero rows is an "empty"
        # answer — a normal application state, not an error.
        if result is not None and result.row_count == 0:
            return MessageStatus.EMPTY
        return MessageStatus.COMPLETED
    # Unknown status: treat conservatively as in-progress so the client keeps
    # polling rather than crashing.
    return MessageStatus.IN_PROGRESS


def normalize_message(
    message: Any,
    *,
    space_id: str | None = None,
    query_result: Any = None,
    max_rows: int = 2000,
) -> GenieMessage:
    """Normalize a Genie message (+ optional query result) into ``GenieMessage``."""
    msg = _as_dict(message) or {}

    conversation_id = str(_get(msg, "conversation_id", "") or "")
    message_id = str(_get(msg, "id") or _get(msg, "message_id") or "")
    raw_status = _get(msg, "status")

    attachments = _get(msg, "attachments") or []
    answer_text: str | None = None
    sql: str | None = None
    query_description: str | None = None
    attachment_id: str | None = None
    statement_id: str | None = None
    follow_ups: list[str] = []

    for att in attachments:
        att = _as_dict(att)
        att_id = _get(att, "attachment_id") or _get(att, "id")
        text = _get(att, "text")
        query = _get(att, "query")

        if text:
            text = _as_dict(text)
            content = _get(text, "content")
            purpose = _get(att, "purpose") or _get(text, "purpose")
            if purpose == _FOLLOW_UP_PURPOSE:
                if content:
                    follow_ups.append(str(content).strip())
            elif purpose in _ANSWER_PURPOSES and content and answer_text is None:
                answer_text = str(content)
                attachment_id = attachment_id or att_id

        if query and sql is None:
            query = _as_dict(query)
            sql = _get(query, "query")
            query_description = _get(query, "description")
            statement_id = _get(query, "statement_id") or statement_id
            attachment_id = att_id or attachment_id

    result = None
    if query_result is not None:
        result = normalize_query_result(query_result, max_rows=max_rows)

    status = _map_status(raw_status, result)

    error_obj = _get(msg, "error")
    error_text = None
    if error_obj:
        error_obj = _as_dict(error_obj)
        error_text = _get(error_obj, "error") if isinstance(error_obj, dict) else None
        error_text = error_text or (
            error_obj if isinstance(error_obj, str) else "Genie could not answer this question."
        )
    if status == MessageStatus.FAILED and not error_text:
        error_text = "Genie could not answer this question."

    return GenieMessage(
        conversation_id=conversation_id,
        message_id=message_id,
        status=status,
        answer_text=answer_text,
        sql=sql,
        query_description=query_description,
        result=result,
        suggested_follow_ups=follow_ups,
        is_empty=status == MessageStatus.EMPTY,
        error=error_text,
        provenance=Provenance(
            conversation_id=conversation_id or None,
            message_id=message_id or None,
            attachment_id=attachment_id,
            statement_id=statement_id,
            space_id=space_id,
        ),
    )


def has_query_attachment(message: Any) -> tuple[str | None, str | None]:
    """Return ``(attachment_id, statement_id)`` of the first query attachment."""
    msg = _as_dict(message) or {}
    for att in _get(msg, "attachments") or []:
        att = _as_dict(att)
        query = _get(att, "query")
        if query:
            query = _as_dict(query)
            return (
                _get(att, "attachment_id") or _get(att, "id"),
                _get(query, "statement_id"),
            )
    return None, None
