"""Ask ChicagoPulse — Genie conversation endpoints."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException

from ..config import Settings
from ..deps import current_settings, get_genie_client
from ..genie.client import GenieClient
from ..models import (
    ConversationCreated,
    FeedbackRating,
    FeedbackReason,
    FollowUpRequest,
    GenieMessage,
    MessageCreated,
    MessageFeedbackRequest,
    MessageFeedbackResponse,
    StartConversationRequest,
)

logger = logging.getLogger("chicagopulse.api")
router = APIRouter(prefix="/conversations")

_FEEDBACK_REASON_LABELS = {
    FeedbackReason.INCORRECT_DATA: "Incorrect data",
    FeedbackReason.MISUNDERSTOOD_QUESTION: "Misunderstood question",
    FeedbackReason.WRONG_TIME_OR_SCOPE: "Wrong time or scope",
    FeedbackReason.POOR_VISUALIZATION: "Poor visualization",
    FeedbackReason.OTHER: "Other",
}


def _validate_question(question: str, settings: Settings) -> str:
    text = (question or "").strip()
    if not text:
        raise HTTPException(status_code=422, detail="A question is required.")
    if len(text) > settings.max_question_length:
        raise HTTPException(
            status_code=422,
            detail=f"Question is too long (max {settings.max_question_length} characters).",
        )
    return text


@router.post("", response_model=ConversationCreated)
def start_conversation(
    body: StartConversationRequest,
    settings: Settings = Depends(current_settings),
    client: GenieClient = Depends(get_genie_client),
) -> ConversationCreated:
    question = _validate_question(body.question, settings)
    try:
        message = client.start(question)
    except Exception:
        logger.exception("Genie start_conversation failed")
        raise HTTPException(status_code=502, detail="Unable to reach Genie. Please retry.")
    return ConversationCreated(
        conversation_id=message.conversation_id,
        message_id=message.message_id,
        status=message.status,
    )


@router.post("/{conversation_id}/messages", response_model=MessageCreated)
def create_message(
    conversation_id: str,
    body: FollowUpRequest,
    settings: Settings = Depends(current_settings),
    client: GenieClient = Depends(get_genie_client),
) -> MessageCreated:
    question = _validate_question(body.question, settings)
    try:
        message = client.follow_up(conversation_id, question)
    except Exception:
        logger.exception("Genie create_message failed")
        raise HTTPException(status_code=502, detail="Unable to reach Genie. Please retry.")
    return MessageCreated(
        conversation_id=message.conversation_id or conversation_id,
        message_id=message.message_id,
        status=message.status,
    )


@router.get("/{conversation_id}/messages/{message_id}", response_model=GenieMessage)
def get_message(
    conversation_id: str,
    message_id: str,
    client: GenieClient = Depends(get_genie_client),
) -> GenieMessage:
    try:
        return client.poll(conversation_id, message_id)
    except Exception:
        logger.exception("Genie get_message failed")
        raise HTTPException(status_code=502, detail="Unable to reach Genie. Please retry.")


def _feedback_comment(body: MessageFeedbackRequest) -> str | None:
    comment = (body.comment or "").strip()
    if body.rating != FeedbackRating.NEGATIVE:
        if body.reason is not None or comment:
            raise HTTPException(
                status_code=422,
                detail="Reason and comment are only accepted with negative feedback.",
            )
        return None
    if body.reason is None:
        raise HTTPException(status_code=422, detail="Choose a reason for negative feedback.")
    if body.reason == FeedbackReason.OTHER and not comment:
        raise HTTPException(status_code=422, detail="Add a comment when the reason is Other.")
    reason = _FEEDBACK_REASON_LABELS[body.reason]
    return f"Reason: {reason}" + (f"\n\n{comment}" if comment else "")


@router.post(
    "/{conversation_id}/messages/{message_id}/feedback",
    response_model=MessageFeedbackResponse,
)
def send_message_feedback(
    conversation_id: str,
    message_id: str,
    body: MessageFeedbackRequest,
    client: GenieClient = Depends(get_genie_client),
) -> MessageFeedbackResponse:
    comment = _feedback_comment(body)
    try:
        rating = client.feedback(conversation_id, message_id, body.rating, comment)
    except Exception:
        logger.exception("Genie send_message_feedback failed")
        raise HTTPException(status_code=502, detail="Unable to save feedback. Please retry.")
    return MessageFeedbackResponse(rating=rating)
