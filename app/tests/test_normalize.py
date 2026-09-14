"""Unit tests for Genie response normalization."""

from server.genie.normalize import (
    has_query_attachment,
    normalize_message,
    normalize_query_result,
)
from server.models import MessageStatus

STATEMENT_RESPONSE = {
    "manifest": {
        "schema": {
            "columns": [
                {"name": "community_area_name", "type_text": "STRING"},
                {"name": "total", "type_text": "BIGINT"},
            ]
        },
        "total_row_count": 2,
        "truncated": False,
    },
    "result": {"data_array": [["Austin", 4820], ["Lake View", 5230]], "row_count": 2},
}


def _completed_message(with_query=True, follow_ups=True):
    attachments = [
        {
            "attachment_id": "a1",
            "purpose": "TEXT_ATTACHMENT_PURPOSE_ANSWER",
            "text": {"content": "Here are the top neighborhoods."},
        }
    ]
    if with_query:
        attachments.append(
            {
                "attachment_id": "a2",
                "query": {
                    "query": "SELECT 1",
                    "description": "desc",
                    "statement_id": "stmt-1",
                },
            }
        )
    if follow_ups:
        attachments.append(
            {
                "attachment_id": "a3",
                "purpose": "FOLLOW_UP_QUESTION",
                "text": {"content": "What about last year?"},
            }
        )
    return {
        "conversation_id": "c1",
        "id": "m1",
        "status": "COMPLETED",
        "attachments": attachments,
    }


def test_completed_with_result():
    msg = normalize_message(_completed_message(), space_id="s1", query_result=STATEMENT_RESPONSE)
    assert msg.status == MessageStatus.COMPLETED
    assert msg.answer_text == "Here are the top neighborhoods."
    assert msg.sql == "SELECT 1"
    assert msg.result is not None
    assert msg.result.row_count == 2
    assert [c.name for c in msg.result.columns] == ["community_area_name", "total"]
    assert msg.suggested_follow_ups == ["What about last year?"]
    assert msg.provenance.statement_id == "stmt-1"
    assert msg.provenance.space_id == "s1"
    assert msg.is_empty is False


def test_completed_empty_result_maps_to_empty():
    empty = {
        "manifest": {"schema": {"columns": []}, "total_row_count": 0},
        "result": {"data_array": [], "row_count": 0},
    }
    msg = normalize_message(_completed_message(), query_result=empty)
    assert msg.status == MessageStatus.EMPTY
    assert msg.is_empty is True


def test_failed_message_has_error():
    raw = {
        "conversation_id": "c1",
        "id": "m1",
        "status": "FAILED",
        "error": {"error": "boom"},
        "attachments": None,
    }
    msg = normalize_message(raw)
    assert msg.status == MessageStatus.FAILED
    assert msg.error == "boom"


def test_in_progress_statuses():
    for status in ["SUBMITTED", "EXECUTING_QUERY", "ASKING_AI", "PENDING_WAREHOUSE"]:
        raw = {"conversation_id": "c", "id": "m", "status": status}
        assert normalize_message(raw).status == MessageStatus.IN_PROGRESS


def test_unknown_status_is_in_progress():
    raw = {"conversation_id": "c", "id": "m", "status": "SOMETHING_NEW"}
    assert normalize_message(raw).status == MessageStatus.IN_PROGRESS


def test_malformed_message_does_not_crash():
    msg = normalize_message({})
    assert msg.status == MessageStatus.IN_PROGRESS
    assert msg.answer_text is None
    assert msg.result is None


def test_query_result_truncation():
    big = {
        "manifest": {"schema": {"columns": [{"name": "x", "type_text": "INT"}]}},
        "result": {"data_array": [[i] for i in range(10)]},
    }
    qr = normalize_query_result(big, max_rows=3)
    assert qr is not None
    assert len(qr.rows) == 3
    assert qr.truncated is True


def test_has_query_attachment():
    aid, sid = has_query_attachment(_completed_message())
    assert aid == "a2"
    assert sid == "stmt-1"
    aid2, _ = has_query_attachment(_completed_message(with_query=False))
    assert aid2 is None
