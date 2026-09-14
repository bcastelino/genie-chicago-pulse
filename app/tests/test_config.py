"""Configuration safety guards, including production mock-mode prevention."""

import pytest

from server.config import ConfigurationError, Settings, _validate


def test_production_with_mock_mode_refuses_to_start():
    settings = Settings(environment="production", mock_mode=True)
    with pytest.raises(ConfigurationError):
        _validate(settings)


def test_production_missing_bindings_refuses_to_start():
    settings = Settings(
        environment="production",
        mock_mode=False,
        genie_space_id=None,
        databricks_warehouse_id=None,
    )
    with pytest.raises(ConfigurationError):
        _validate(settings)


def test_production_with_bindings_ok():
    settings = Settings(
        environment="production",
        mock_mode=False,
        genie_space_id="space",
        databricks_warehouse_id="wh",
        databricks_job_id=123,
    )
    _validate(settings)  # should not raise


def test_production_missing_job_binding_refuses_to_start():
    settings = Settings(
        environment="production",
        mock_mode=False,
        genie_space_id="space",
        databricks_warehouse_id="wh",
        databricks_job_id=None,
    )
    with pytest.raises(ConfigurationError, match="DATABRICKS_JOB_ID"):
        _validate(settings)


def test_development_mock_mode_ok():
    _validate(Settings(environment="development", mock_mode=True))
