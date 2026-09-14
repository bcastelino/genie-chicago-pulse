"""Mock Genie and Warehouse providers that mirror the real interfaces."""

from __future__ import annotations

import uuid
from typing import Any

from ..models import PipelineRunResponse, PipelineTaskResponse, QueryResult
from . import fixtures


class MockGenieProvider:
    """Simulates the Genie conversation lifecycle deterministically.

    A message reports IN_PROGRESS on its first poll and a terminal state
    thereafter, so the UI's progress + polling paths are exercised.
    """

    def __init__(self) -> None:
        self._questions: dict[str, str] = {}
        self._polls: dict[str, int] = {}
        self._feedback: dict[tuple[str, str], dict[str, str | None]] = {}

    def _new_message(self, conversation_id: str, content: str) -> dict[str, Any]:
        message_id = uuid.uuid4().hex
        self._questions[message_id] = content
        self._polls[message_id] = 0
        return {
            "conversation_id": conversation_id,
            "id": message_id,
            "status": "IN_PROGRESS",
            "content": content,
            "attachments": None,
        }

    def start_conversation(self, content: str) -> dict[str, Any]:
        return self._new_message(uuid.uuid4().hex, content)

    def create_message(self, conversation_id: str, content: str) -> dict[str, Any]:
        return self._new_message(conversation_id, content)

    def get_message(self, conversation_id: str, message_id: str) -> dict[str, Any]:
        question = self._questions.get(message_id, "")
        self._polls[message_id] = self._polls.get(message_id, 0) + 1
        if self._polls[message_id] < 2:
            return {
                "conversation_id": conversation_id,
                "id": message_id,
                "status": "EXECUTING_QUERY",
                "attachments": None,
            }

        q = question.lower()
        if "fail" in q or "error" in q:
            return {
                "conversation_id": conversation_id,
                "id": message_id,
                "status": "FAILED",
                "error": {"error": "The generated query could not be executed."},
                "attachments": None,
            }

        text = (
            "In the latest completed month, Austin, Lake View, and West Town "
            "recorded the highest 311 service request volumes across Chicago."
        )
        return {
            "conversation_id": conversation_id,
            "id": message_id,
            "status": "COMPLETED",
            "attachments": [
                {
                    "attachment_id": "att-text",
                    "purpose": "TEXT_ATTACHMENT_PURPOSE_ANSWER",
                    "text": {"content": text},
                },
                {
                    "attachment_id": "att-query",
                    "query": {
                        "query": (
                            "SELECT community_area_name, MEASURE(total_311_requests) "
                            "AS total_311_requests\n"
                            "FROM workspace.chicagopulse.mv_neighborhood_pulse\n"
                            "WHERE metric_month = (SELECT MAX(metric_month) "
                            "FROM workspace.chicagopulse.mv_neighborhood_pulse)\n"
                            "GROUP BY community_area_name\n"
                            "ORDER BY total_311_requests DESC\nLIMIT 5"
                        ),
                        "description": "Top neighborhoods by 311 requests in the latest month.",
                        "statement_id": "stmt-" + message_id[:8],
                    },
                },
                {
                    "attachment_id": "att-follow",
                    "purpose": "FOLLOW_UP_QUESTION",
                    "text": {"content": "How did these neighborhoods change month over month?"},
                },
            ],
        }

    def get_query_result(
        self, conversation_id: str, message_id: str, attachment_id: str
    ) -> dict[str, Any] | None:
        question = self._questions.get(message_id, "").lower()
        columns = [
            {"name": "community_area_name", "type_text": "STRING"},
            {"name": "total_311_requests", "type_text": "BIGINT"},
        ]
        if "empty" in question:
            data: list[list[Any]] = []
        else:
            data = [
                ["Lake View", 5230],
                ["West Town", 4990],
                ["Austin", 4820],
                ["Lincoln Park", 4110],
                ["Logan Square", 3980],
            ]
        return {
            "manifest": {
                "schema": {"columns": columns},
                "total_row_count": len(data),
                "truncated": False,
            },
            "result": {"data_array": data, "row_count": len(data)},
        }

    def get_space(self) -> dict[str, Any]:
        return {
            "space_id": "mock-space",
            "title": "ChicagoPulse",
            "description": (
                "Chicago neighborhood analytics for 311 requests, business licenses, "
                "building permits, and violations.\n\n"
                "**Capabilities:** Compare completed monthly trends across official "
                "Community Areas.\n\n"
                "**Limitations:** Not real time and not intended for address-level analysis."
            ),
            "warehouse_id": "mock-warehouse",
            "update_time": "2026-08-25T15:16:07.929Z",
        }

    def send_feedback(
        self, conversation_id: str, message_id: str, rating: str, comment: str | None
    ) -> dict[str, Any]:
        key = (conversation_id, message_id)
        if rating == "NONE":
            self._feedback.pop(key, None)
        else:
            self._feedback[key] = {"rating": rating, "comment": comment}
        return {}

    def workspace_host(self) -> str:
        return "https://example.databricks.com"


class MockWarehouseProvider:
    """Returns fixture rows shaped exactly like the real query outputs."""

    def run(self, sql: str, params: dict[str, Any] | None = None) -> QueryResult:
        params = params or {}
        s = " ".join(sql.split())  # collapse whitespace for matching

        if "geometry_geojson" in s:
            return _qr(
                ["community_area", "community_area_name", "geometry_geojson"],
                fixtures.geo_rows(),
            )
        if "gold_dim_community_area" in s:
            return _qr(
                ["community_area", "community_area_name"],
                [[ca, name] for ca, name in fixtures.NEIGHBORHOODS],
            )
        if "gold_latest_neighborhood_pulse" in s and "ca" not in params:
            # Map query: one 311 value per area for the latest completed month.
            rows = [
                [ca, name, fixtures.pulse_for(ca)["service_request_count"] or 2000]
                for ca, name in fixtures.NEIGHBORHOODS
            ]
            return _qr(["community_area", "community_area_name", "service_request_count"], rows)
        if "gold_latest_neighborhood_pulse" in s:
            ca = int(params.get("ca", 25))
            p = fixtures.pulse_for(ca)
            row = [
                fixtures.LATEST_MONTH, ca, fixtures.name_for(ca),
                p["service_request_count"], p["previous_month_request_count"],
                p["request_count_mom_pct"], p["open_request_count"],
                p["closed_request_count"], p["avg_resolution_days"],
                p["new_license_issues"], p["previous_month_new_license_issues"],
                p["permit_count"], p["previous_month_permit_count"],
                p["new_construction_permit_count"], p["total_permit_fees"],
                p["violation_count"], p["previous_month_violation_count"],
                p["open_violation_count"], p["business_data_available"],
                p["permit_data_available"], p["violation_data_available"],
            ]
            cols = [
                "metric_month", "community_area", "community_area_name",
                "service_request_count", "previous_month_request_count",
                "request_count_mom_pct", "open_request_count", "closed_request_count",
                "avg_resolution_days", "new_license_issues",
                "previous_month_new_license_issues", "permit_count",
                "previous_month_permit_count", "new_construction_permit_count",
                "total_permit_fees", "violation_count", "previous_month_violation_count",
                "open_violation_count", "business_data_available",
                "permit_data_available", "violation_data_available",
            ]
            return _qr(cols, [row])
        if "gold_service_type_trends" in s:
            ca = int(params.get("ca", 25))
            return _qr(["category", "value"], fixtures.service_types_for(ca))
        if "ORDER BY metric_month" in s and "gold_neighborhood_pulse" in s and "ca" in params:
            ca = int(params.get("ca", 25))
            return _qr(["metric_month", "service_request_count"], fixtures.trend_for(ca))
        if "community_area IN" in s or any(k.startswith("ca") for k in params):
            cas = [int(v) for k, v in params.items() if k.startswith("ca")]
            rows = [_compare_row(ca) for ca in cas]
            cols = [
                "metric_month", "community_area", "community_area_name",
                "service_request_count", "request_count_mom_pct", "open_request_count",
                "avg_resolution_days", "new_license_issues", "permit_count",
                "new_construction_permit_count", "total_permit_fees", "violation_count",
                "open_violation_count", "business_data_available",
                "permit_data_available", "violation_data_available",
            ]
            return _qr(cols, rows)
        if "MAX(metric_month)" in s and "gold_neighborhood_pulse" in s:
            return _qr(["metric_month"], [[fixtures.LATEST_MONTH]])
        if "gold_data_freshness" in s:
            return _qr(
                ["dataset", "row_count", "min_date", "max_date"],
                [list(r) for r in fixtures.FRESHNESS],
            )
        if "etl_dataset_runs" in s:
            return _qr(
                ["dataset", "last_ingested_at"],
                [[name, ts] for name, ts in fixtures.SUCCESSFUL_DATASET_RUNS.items()],
            )
        if "etl_pipeline_runs" in s:
            run = fixtures.PIPELINE_RUN
            columns = [
                "run_id", "started_at", "completed_at", "status", "message",
                "last_success_at",
            ]
            return _qr(columns, [[run[column] for column in columns]])
        return QueryResult()


class MockPipelineRunner:
    """Deterministic queued → running → successful job lifecycle for the UI."""

    def __init__(self) -> None:
        self._polls = 0
        self._run_id = 424242

    def trigger(self) -> PipelineRunResponse:
        self._polls = 0
        return PipelineRunResponse(
            run_id=self._run_id,
            life_cycle_state="PENDING",
            started_new=True,
            tasks=self._tasks(0),
        )

    def get(self, run_id: int) -> PipelineRunResponse:
        from ..pipeline.jobs import PipelineRunNotFound

        if run_id != self._run_id:
            raise PipelineRunNotFound
        self._polls += 1
        done = self._polls >= 4
        return PipelineRunResponse(
            run_id=run_id,
            life_cycle_state="TERMINATED" if done else "RUNNING",
            result_state="SUCCESS" if done else None,
            run_page_url=f"https://example.databricks.com/jobs/{run_id}",
            start_time="2026-08-27T14:00:00Z",
            end_time="2026-08-27T14:06:19Z" if done else None,
            duration_ms=379000 if done else self._polls * 90000,
            tasks=self._tasks(self._polls),
        )

    @staticmethod
    def _tasks(step: int) -> list[PipelineTaskResponse]:
        definitions = [
            ("incremental_ingestion", "Incremental ingestion"),
            ("transform_refresh", "Transform refresh"),
            ("validation", "Validation"),
        ]
        tasks = []
        for index, (key, label) in enumerate(definitions):
            if step > index + 1:
                state, result = "TERMINATED", "SUCCESS"
            elif step == index + 1:
                state, result = "RUNNING", None
            else:
                state, result = "PENDING", None
            if step >= 4:
                state, result = "TERMINATED", "SUCCESS"
            tasks.append(
                PipelineTaskResponse(
                    task_key=key,
                    label=label,
                    life_cycle_state=state,
                    result_state=result,
                )
            )
        return tasks


def _compare_row(ca: int) -> list[Any]:
    p = fixtures.pulse_for(ca)
    return [
        fixtures.LATEST_MONTH, ca, fixtures.name_for(ca),
        p["service_request_count"], p["request_count_mom_pct"], p["open_request_count"],
        p["avg_resolution_days"], p["new_license_issues"], p["permit_count"],
        p["new_construction_permit_count"], p["total_permit_fees"], p["violation_count"],
        p["open_violation_count"], p["business_data_available"],
        p["permit_data_available"], p["violation_data_available"],
    ]


def _qr(columns: list[str], rows: list[list[Any]]) -> QueryResult:
    from ..models import Column

    return QueryResult(
        columns=[Column(name=c, type="string") for c in columns],
        rows=rows,
        row_count=len(rows),
        truncated=False,
    )
