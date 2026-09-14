"""Unit tests for the allowlisted Databricks Job runner."""

from types import SimpleNamespace

import pytest

from server.pipeline.jobs import DatabricksPipelineRunner, PipelineRunNotFound, _normalize_run


def _runner(jobs) -> DatabricksPipelineRunner:
    runner = DatabricksPipelineRunner.__new__(DatabricksPipelineRunner)
    runner.job_id = 123
    runner._w = SimpleNamespace(jobs=jobs)
    return runner


def test_trigger_starts_job_when_no_run_is_active():
    jobs = SimpleNamespace(
        list_runs=lambda **kwargs: iter([]),
        run_now=lambda **kwargs: SimpleNamespace(
            response=SimpleNamespace(run_id=456)
        ),
    )
    result = _runner(jobs).trigger()
    assert result.run_id == 456
    assert result.life_cycle_state == "PENDING"
    assert result.started_new is True
    assert [task.task_key for task in result.tasks] == [
        "incremental_ingestion",
        "transform_refresh",
        "validation",
    ]


def test_trigger_returns_existing_active_run_instead_of_queueing_duplicate():
    active = SimpleNamespace(
        job_id=123,
        run_id=789,
        state=SimpleNamespace(
            life_cycle_state=SimpleNamespace(value="RUNNING"),
            result_state=None,
            state_message="Running",
        ),
        run_page_url="https://example.databricks.com/run/789",
    )

    class Jobs:
        def list_runs(self, **kwargs):
            return iter([active])

        def run_now(self, **kwargs):
            raise AssertionError("run_now must not be called for an active job")

    result = _runner(Jobs()).trigger()
    assert result.run_id == 789
    assert result.life_cycle_state == "RUNNING"
    assert result.started_new is False


def test_run_normalization_whitelists_and_orders_task_state():
    run = SimpleNamespace(
        job_id=123,
        run_id=900,
        start_time=1_787_839_256_948,
        end_time=1_787_839_636_395,
        run_duration=379_447,
        run_page_url="https://example.databricks.com/run/900",
        state=SimpleNamespace(life_cycle_state="TERMINATED", result_state="SUCCESS"),
        tasks=[
            SimpleNamespace(
                task_key="validation",
                start_time=1_787_839_605_742,
                end_time=1_787_839_635_972,
                state=SimpleNamespace(life_cycle_state="TERMINATED", result_state="SUCCESS"),
                notebook_task=SimpleNamespace(notebook_path="/secret/path"),
            ),
            SimpleNamespace(
                task_key="unknown_internal_task",
                state=SimpleNamespace(life_cycle_state="TERMINATED", result_state="SUCCESS"),
            ),
            SimpleNamespace(
                task_key="incremental_ingestion",
                start_time=1_787_839_257_018,
                end_time=1_787_839_490_196,
                state=SimpleNamespace(life_cycle_state="TERMINATED", result_state="SUCCESS"),
            ),
            SimpleNamespace(
                task_key="transform_refresh",
                state=SimpleNamespace(life_cycle_state="RUNNING", result_state=None),
            ),
        ],
    )

    result = _normalize_run(run, expected_job_id=123)

    assert [task.task_key for task in result.tasks] == [
        "incremental_ingestion",
        "transform_refresh",
        "validation",
    ]
    assert result.tasks[1].life_cycle_state == "RUNNING"
    assert result.tasks[0].duration_ms == 233_178
    payload = result.model_dump()
    assert "job_id" not in payload
    assert "notebook_path" not in str(payload)
    assert "state_message" not in str(payload)


def test_run_normalization_rejects_a_different_job():
    run = SimpleNamespace(job_id=999, run_id=900)
    with pytest.raises(PipelineRunNotFound):
        _normalize_run(run, expected_job_id=123)
