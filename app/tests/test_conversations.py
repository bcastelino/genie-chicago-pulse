"""Conversation API contract tests (mock provider)."""


def _drive_to_terminal(client, conv_id, msg_id, max_polls=6):
    status = "IN_PROGRESS"
    body = None
    for _ in range(max_polls):
        body = client.get(f"/api/conversations/{conv_id}/messages/{msg_id}").json()
        status = body["status"]
        if status != "IN_PROGRESS":
            break
    return body


def test_start_and_poll_to_completion(client):
    start = client.post("/api/conversations", json={"question": "Top neighborhoods by 311?"})
    assert start.status_code == 200
    created = start.json()
    assert created["status"] == "IN_PROGRESS"

    body = _drive_to_terminal(client, created["conversation_id"], created["message_id"])
    assert body["status"] == "COMPLETED"
    assert body["sql"]
    assert body["result"]["row_count"] == 5
    assert body["answer_text"]
    assert body["provenance"]["conversation_id"] == created["conversation_id"]


def test_follow_up_reuses_conversation(client):
    start = client.post("/api/conversations", json={"question": "Top neighborhoods?"}).json()
    conv = start["conversation_id"]
    follow = client.post(
        f"/api/conversations/{conv}/messages", json={"question": "And by violations?"}
    )
    assert follow.status_code == 200
    assert follow.json()["conversation_id"] == conv


def test_empty_result_is_normal_state(client):
    start = client.post("/api/conversations", json={"question": "empty please"}).json()
    body = _drive_to_terminal(client, start["conversation_id"], start["message_id"])
    assert body["status"] == "EMPTY"
    assert body["is_empty"] is True


def test_failed_query_surfaces_error(client):
    start = client.post("/api/conversations", json={"question": "please fail this"}).json()
    body = _drive_to_terminal(client, start["conversation_id"], start["message_id"])
    assert body["status"] == "FAILED"
    assert body["error"]


def test_empty_question_rejected(client):
    resp = client.post("/api/conversations", json={"question": "   "})
    assert resp.status_code == 422


def test_oversized_question_rejected(client):
    resp = client.post("/api/conversations", json={"question": "x" * 1001})
    assert resp.status_code == 422


def test_genie_agent_metadata(client):
    response = client.get("/api/genie-agent")
    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "ChicagoPulse"
    assert body["space_id"] == "mock-space"
    assert body["warehouse_id"] == "mock-warehouse"
    assert body["space_url"] == "https://example.databricks.com/genie/rooms/mock-space"
    assert "Limitations" in body["description"]


def test_genie_agent_metadata_failure_is_sanitized(client):
    from server.deps import get_genie_client
    from server.main import app

    class BrokenClient:
        def info(self):
            raise RuntimeError("sensitive upstream detail")

    app.dependency_overrides[get_genie_client] = lambda: BrokenClient()
    try:
        response = client.get("/api/genie-agent")
    finally:
        app.dependency_overrides.pop(get_genie_client, None)

    assert response.status_code == 502
    assert response.json() == {"detail": "Unable to load Genie Agent details."}


def test_positive_feedback_is_accepted(client):
    response = client.post(
        "/api/conversations/conversation-1/messages/message-1/feedback",
        json={"rating": "POSITIVE", "reason": None, "comment": None},
    )
    assert response.status_code == 200
    assert response.json() == {"rating": "POSITIVE"}


def test_negative_feedback_requires_reason(client):
    response = client.post(
        "/api/conversations/conversation-1/messages/message-1/feedback",
        json={"rating": "NEGATIVE", "reason": None, "comment": "Incorrect total"},
    )
    assert response.status_code == 422
    assert response.json() == {"detail": "Choose a reason for negative feedback."}


def test_other_feedback_requires_comment(client):
    response = client.post(
        "/api/conversations/conversation-1/messages/message-1/feedback",
        json={"rating": "NEGATIVE", "reason": "OTHER", "comment": "   "},
    )
    assert response.status_code == 422
    assert response.json() == {"detail": "Add a comment when the reason is Other."}


def test_feedback_comment_is_normalized_before_forwarding(client):
    from server.deps import get_genie_client
    from server.main import app

    class RecordingClient:
        call = None

        def feedback(self, conversation_id, message_id, rating, comment):
            self.call = (conversation_id, message_id, rating, comment)
            return rating

    recording = RecordingClient()
    app.dependency_overrides[get_genie_client] = lambda: recording
    try:
        response = client.post(
            "/api/conversations/conversation-1/messages/message-1/feedback",
            json={
                "rating": "NEGATIVE",
                "reason": "INCORRECT_DATA",
                "comment": "  The total is too high.  ",
            },
        )
    finally:
        app.dependency_overrides.pop(get_genie_client, None)

    assert response.status_code == 200
    assert recording.call[0:2] == ("conversation-1", "message-1")
    assert recording.call[2].value == "NEGATIVE"
    assert recording.call[3] == "Reason: Incorrect data\n\nThe total is too high."


def test_positive_and_none_reject_reason_or_comment(client):
    for payload in (
        {"rating": "POSITIVE", "reason": "INCORRECT_DATA", "comment": None},
        {"rating": "NONE", "reason": None, "comment": "clear it"},
    ):
        response = client.post(
            "/api/conversations/conversation-1/messages/message-1/feedback",
            json=payload,
        )
        assert response.status_code == 422


def test_feedback_rejects_unknown_reason_and_oversized_comment(client):
    unknown = client.post(
        "/api/conversations/conversation-1/messages/message-1/feedback",
        json={"rating": "NEGATIVE", "reason": "SECRET_REASON", "comment": None},
    )
    oversized = client.post(
        "/api/conversations/conversation-1/messages/message-1/feedback",
        json={"rating": "NEGATIVE", "reason": "OTHER", "comment": "x" * 501},
    )
    assert unknown.status_code == 422
    assert oversized.status_code == 422


def test_feedback_upstream_failure_is_sanitized(client):
    from server.deps import get_genie_client
    from server.main import app

    class BrokenClient:
        def feedback(self, *args):
            raise RuntimeError("secret upstream response")

    app.dependency_overrides[get_genie_client] = lambda: BrokenClient()
    try:
        response = client.post(
            "/api/conversations/conversation-1/messages/message-1/feedback",
            json={"rating": "POSITIVE", "reason": None, "comment": None},
        )
    finally:
        app.dependency_overrides.pop(get_genie_client, None)

    assert response.status_code == 502
    assert response.json() == {"detail": "Unable to save feedback. Please retry."}


def test_feedback_provider_encodes_identifiers():
    from server.genie.client import DatabricksGenieProvider

    provider = DatabricksGenieProvider.__new__(DatabricksGenieProvider)
    provider.space_id = "space/id"
    calls = []
    provider._do = lambda method, path, body=None: calls.append((method, path, body)) or {}

    provider.send_feedback("conversation/id", "message id", "NEGATIVE", "Reason: Other")

    assert calls == [
        (
            "POST",
            "/api/2.0/genie/spaces/space%2Fid/conversations/conversation%2Fid/messages/message%20id/feedback",
            {"rating": "NEGATIVE", "comment": "Reason: Other"},
        )
    ]
