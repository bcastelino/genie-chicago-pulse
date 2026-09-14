"""Provider wiring. Selects mock or real providers based on settings."""

from __future__ import annotations

import functools

from .config import Settings, get_settings
from .data.warehouse import DatabricksWarehouseProvider, WarehouseProvider
from .genie.client import DatabricksGenieProvider, GenieClient
from .pipeline.jobs import DatabricksPipelineRunner, PipelineRunner


@functools.lru_cache(maxsize=1)
def get_genie_client() -> GenieClient:
    settings = get_settings()
    if settings.mock_mode:
        from .mock.providers import MockGenieProvider

        return GenieClient(MockGenieProvider(), settings, space_id="mock-space")

    if not settings.genie_space_id:
        raise RuntimeError("GENIE_SPACE_ID is required when mock mode is disabled.")

    provider = DatabricksGenieProvider(
        space_id=settings.genie_space_id,
        profile=settings.databricks_profile,
        host=settings.databricks_host,
    )
    return GenieClient(provider, settings, space_id=settings.genie_space_id)


@functools.lru_cache(maxsize=1)
def get_warehouse() -> WarehouseProvider:
    settings = get_settings()
    if settings.mock_mode:
        from .mock.providers import MockWarehouseProvider

        return MockWarehouseProvider()

    if not settings.databricks_warehouse_id:
        raise RuntimeError("DATABRICKS_WAREHOUSE_ID is required when mock mode is disabled.")

    return DatabricksWarehouseProvider(
        warehouse_id=settings.databricks_warehouse_id,
        settings=settings,
        profile=settings.databricks_profile,
        host=settings.databricks_host,
    )


@functools.lru_cache(maxsize=1)
def get_pipeline_runner() -> PipelineRunner:
    settings = get_settings()
    if settings.mock_mode:
        from .mock.providers import MockPipelineRunner

        return MockPipelineRunner()

    if settings.databricks_job_id is None:
        raise RuntimeError("DATABRICKS_JOB_ID is required when mock mode is disabled.")

    return DatabricksPipelineRunner(
        job_id=settings.databricks_job_id,
        profile=settings.databricks_profile,
        host=settings.databricks_host,
    )


def reset_caches() -> None:
    """Test helper to clear cached singletons."""
    get_genie_client.cache_clear()
    get_warehouse.cache_clear()
    get_pipeline_runner.cache_clear()
    get_settings.cache_clear()


def current_settings() -> Settings:
    return get_settings()
