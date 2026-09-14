"""Normalized response contracts returned to the React client.

These are the *only* shapes the frontend depends on. Databricks/Genie
responses are normalized into these models before leaving the server so that
provider changes never leak into the UI.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = "ok"
    mock_mode: bool
    environment: str
    version: str


class MessageStatus(str, Enum):
    """Normalized terminal + in-progress states for a Genie message."""

    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    EMPTY = "EMPTY"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


class Column(BaseModel):
    name: str
    type: str = "string"


class QueryResult(BaseModel):
    columns: list[Column] = Field(default_factory=list)
    rows: list[list[Any]] = Field(default_factory=list)
    row_count: int = 0
    truncated: bool = False


class Provenance(BaseModel):
    """Where an answer came from, for the details panel."""

    conversation_id: str | None = None
    message_id: str | None = None
    attachment_id: str | None = None
    statement_id: str | None = None
    space_id: str | None = None


class GenieMessage(BaseModel):
    """A single normalized assistant turn."""

    conversation_id: str
    message_id: str
    status: MessageStatus
    answer_text: str | None = None
    sql: str | None = None
    query_description: str | None = None
    result: QueryResult | None = None
    suggested_follow_ups: list[str] = Field(default_factory=list)
    is_empty: bool = False
    error: str | None = None
    provenance: Provenance = Field(default_factory=Provenance)


class GenieAgentResponse(BaseModel):
    """Public metadata for the configured Genie Agent."""

    space_id: str
    title: str
    description: str
    warehouse_id: str | None = None
    updated_at: str | None = None
    space_url: str | None = None


class StartConversationRequest(BaseModel):
    question: str


class FollowUpRequest(BaseModel):
    question: str


class ConversationCreated(BaseModel):
    conversation_id: str
    message_id: str
    status: MessageStatus


class MessageCreated(BaseModel):
    conversation_id: str
    message_id: str
    status: MessageStatus


class FeedbackRating(str, Enum):
    POSITIVE = "POSITIVE"
    NEGATIVE = "NEGATIVE"
    NONE = "NONE"


class FeedbackReason(str, Enum):
    INCORRECT_DATA = "INCORRECT_DATA"
    MISUNDERSTOOD_QUESTION = "MISUNDERSTOOD_QUESTION"
    WRONG_TIME_OR_SCOPE = "WRONG_TIME_OR_SCOPE"
    POOR_VISUALIZATION = "POOR_VISUALIZATION"
    OTHER = "OTHER"


class MessageFeedbackRequest(BaseModel):
    rating: FeedbackRating
    reason: FeedbackReason | None = None
    comment: str | None = Field(default=None, max_length=500)


class MessageFeedbackResponse(BaseModel):
    rating: FeedbackRating


class Neighborhood(BaseModel):
    community_area: int
    community_area_name: str


class MetricValue(BaseModel):
    """A single metric with optional month-over-month context.

    `available` is False when the underlying *_data_available flag is false,
    so the UI can render "N/A" rather than a misleading zero.
    """

    key: str
    label: str
    value: float | None = None
    previous_value: float | None = None
    mom_change_pct: float | None = None
    unit: str | None = None
    available: bool = True


class TrendPoint(BaseModel):
    metric_month: str
    value: float | None = None


class CategoryCount(BaseModel):
    category: str
    value: float


class NeighborhoodPulse(BaseModel):
    community_area: int
    community_area_name: str
    metric_month: str | None = None
    reporting_period_label: str | None = None
    metrics: list[MetricValue] = Field(default_factory=list)
    trend_311: list[TrendPoint] = Field(default_factory=list)
    top_service_types: list[CategoryCount] = Field(default_factory=list)


class ComparisonResponse(BaseModel):
    metric_month: str | None = None
    reporting_period_label: str | None = None
    metric_keys: list[MetricValue] = Field(default_factory=list)
    neighborhoods: list[NeighborhoodPulse] = Field(default_factory=list)


class MapMetricPoint(BaseModel):
    community_area: int
    community_area_name: str
    value: float | None = None


class MapMetricResponse(BaseModel):
    metric_month: str | None = None
    reporting_period_label: str | None = None
    metric_label: str
    values: list[MapMetricPoint] = Field(default_factory=list)


class DatasetHealth(BaseModel):
    dataset: str
    socrata_id: str | None = None
    category: str | None = None
    source_url: str | None = None
    usage_status: str = "in_use"
    row_count: int | None = None
    min_date: str | None = None
    max_date: str | None = None
    last_ingested_at: str | None = None


class DataHealthResponse(BaseModel):
    last_refresh_at: str | None = None
    latest_reporting_month: str | None = None
    pipeline_status: str
    datasets: list[DatasetHealth] = Field(default_factory=list)
    metric_explanation: str
    source_notice: str


class PipelineTaskResponse(BaseModel):
    """Normalized state for one allowlisted task in the refresh job."""

    task_key: str
    label: str
    life_cycle_state: str
    result_state: str | None = None
    start_time: str | None = None
    end_time: str | None = None
    duration_ms: int | None = None


class PipelineRunResponse(BaseModel):
    """Safe subset of a run for the single configured refresh job."""

    run_id: int
    life_cycle_state: str
    result_state: str | None = None
    run_page_url: str | None = None
    started_new: bool = False
    start_time: str | None = None
    end_time: str | None = None
    duration_ms: int | None = None
    tasks: list[PipelineTaskResponse] = Field(default_factory=list)


class ErrorResponse(BaseModel):
    error: str
    detail: str | None = None
