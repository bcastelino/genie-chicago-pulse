"""Least-privilege access to the single configured ChicagoPulse refresh job."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, Protocol

from ..models import PipelineRunResponse, PipelineTaskResponse

_TASKS: tuple[tuple[str, str], ...] = (
    ("incremental_ingestion", "Incremental ingestion"),
    ("transform_refresh", "Transform refresh"),
    ("validation", "Validation"),
)


class PipelineRunNotFound(LookupError):
    """The requested run is not part of the configured pipeline job."""


class PipelineRunner(Protocol):
    def trigger(self) -> PipelineRunResponse: ...

    def get(self, run_id: int) -> PipelineRunResponse: ...


def _enum_value(value: Any) -> str | None:
    if value is None:
        return None
    return str(getattr(value, "value", value))


def _timestamp(value: Any) -> str | None:
    if value in (None, 0):
        return None
    try:
        return datetime.fromtimestamp(int(value) / 1000, tz=UTC).isoformat().replace(
            "+00:00", "Z"
        )
    except (TypeError, ValueError, OSError):
        return None


def _duration_ms(item: Any) -> int | None:
    explicit = getattr(item, "run_duration", None)
    if explicit not in (None, 0):
        return int(explicit)
    start = getattr(item, "start_time", None)
    end = getattr(item, "end_time", None)
    if start not in (None, 0) and end not in (None, 0):
        return max(0, int(end) - int(start))
    return None


def _queued_tasks() -> list[PipelineTaskResponse]:
    return [
        PipelineTaskResponse(
            task_key=task_key,
            label=label,
            life_cycle_state="PENDING",
        )
        for task_key, label in _TASKS
    ]


def _normalize_tasks(run: Any) -> list[PipelineTaskResponse]:
    raw_tasks = {
        str(getattr(task, "task_key", "")): task
        for task in (getattr(run, "tasks", None) or [])
    }
    tasks = []
    for task_key, label in _TASKS:
        task = raw_tasks.get(task_key)
        if task is None:
            tasks.append(
                PipelineTaskResponse(
                    task_key=task_key,
                    label=label,
                    life_cycle_state="PENDING",
                )
            )
            continue
        state = getattr(task, "state", None)
        tasks.append(
            PipelineTaskResponse(
                task_key=task_key,
                label=label,
                life_cycle_state=(
                    _enum_value(getattr(state, "life_cycle_state", None)) or "UNKNOWN"
                ),
                result_state=_enum_value(getattr(state, "result_state", None)),
                start_time=_timestamp(getattr(task, "start_time", None)),
                end_time=_timestamp(getattr(task, "end_time", None)),
                duration_ms=_duration_ms(task),
            )
        )
    return tasks


def _normalize_run(run: Any, *, expected_job_id: int) -> PipelineRunResponse:
    job_id = int(run.job_id)
    if job_id != expected_job_id:
        raise PipelineRunNotFound
    state = getattr(run, "state", None)
    return PipelineRunResponse(
        run_id=int(run.run_id),
        life_cycle_state=_enum_value(getattr(state, "life_cycle_state", None)) or "UNKNOWN",
        result_state=_enum_value(getattr(state, "result_state", None)),
        run_page_url=getattr(run, "run_page_url", None),
        started_new=False,
        start_time=_timestamp(getattr(run, "start_time", None)),
        end_time=_timestamp(getattr(run, "end_time", None)),
        duration_ms=_duration_ms(run),
        tasks=_normalize_tasks(run),
    )


class DatabricksPipelineRunner:
    """Starts and observes only the job identified by the App resource binding."""

    def __init__(
        self,
        job_id: int,
        profile: str | None = None,
        host: str | None = None,
    ) -> None:
        from databricks.sdk import WorkspaceClient

        self.job_id = job_id
        kwargs: dict[str, Any] = {}
        if profile:
            kwargs["profile"] = profile
        if host:
            kwargs["host"] = host
        self._w = WorkspaceClient(**kwargs)

    def trigger(self) -> PipelineRunResponse:
        # Avoid stacking duplicate ad-hoc runs when the job is already queued or running.
        active = next(
            self._w.jobs.list_runs(job_id=self.job_id, active_only=True, limit=1),
            None,
        )
        if active is not None:
            return _normalize_run(active, expected_job_id=self.job_id)

        waiter = self._w.jobs.run_now(
            job_id=self.job_id,
            idempotency_token=uuid.uuid4().hex,
        )
        run_id = int(waiter.response.run_id)
        return PipelineRunResponse(
            run_id=run_id,
            life_cycle_state="PENDING",
            started_new=True,
            tasks=_queued_tasks(),
        )

    def get(self, run_id: int) -> PipelineRunResponse:
        try:
            run = self._w.jobs.get_run(run_id=run_id)
        except Exception as exc:
            from databricks.sdk.errors import NotFound

            if isinstance(exc, NotFound):
                raise PipelineRunNotFound from exc
            raise
        return _normalize_run(run, expected_job_id=self.job_id)
