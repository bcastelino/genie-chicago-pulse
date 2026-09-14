"""Application configuration and startup safety guards.

All Databricks identifiers and provider logic live server-side. Resource IDs
are read from the environment (locally via a Databricks CLI profile, in the
deployed app via resource bindings). Nothing here should ever contain a secret
value; only names and non-sensitive identifiers.
"""

from __future__ import annotations

import functools

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-driven settings.

    Populated from process environment (and an optional local .env during
    development). See .env.example for the full list of variable names.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Deployment/runtime
    environment: str = "development"  # "development" | "production"
    mock_mode: bool = False

    # Databricks connection. In the deployed app these arrive via resource
    # bindings; locally they come from the Databricks CLI profile + env.
    databricks_host: str | None = None
    databricks_profile: str | None = None
    genie_space_id: str | None = None
    databricks_warehouse_id: str | None = None
    databricks_job_id: int | None = None

    # Unity Catalog namespace for the governed Gold tables / Metric Views.
    catalog: str = "workspace"
    schema_name: str = "chicagopulse"

    # Bounded polling / query limits.
    genie_poll_timeout_seconds: float = 8.0
    max_question_length: int = 1000
    max_result_rows: int = 2000

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"

    @property
    def namespace(self) -> str:
        return f"{self.catalog}.{self.schema_name}"


class ConfigurationError(RuntimeError):
    """Raised when the process is misconfigured for the target environment."""


@functools.lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    _validate(settings)
    return settings


def _validate(settings: Settings) -> None:
    # The production application must fail at startup if mock mode is enabled.
    if settings.is_production and settings.mock_mode:
        raise ConfigurationError(
            "MOCK_MODE must never be enabled in production. Refusing to start."
        )

    # In a real (non-mock) deployment we require the Genie/Warehouse bindings.
    if not settings.mock_mode:
        missing = [
            name
            for name, value in (
                ("GENIE_SPACE_ID", settings.genie_space_id),
                ("DATABRICKS_WAREHOUSE_ID", settings.databricks_warehouse_id),
                ("DATABRICKS_JOB_ID", settings.databricks_job_id),
            )
            if not value
        ]
        if missing and settings.is_production:
            raise ConfigurationError(
                "Missing required Databricks bindings in production: "
                + ", ".join(missing)
            )
