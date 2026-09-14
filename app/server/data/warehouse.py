"""Read-only SQL Warehouse access.

Only this module executes SQL, and only the allowlisted, parameterized
templates in ``queries.py`` are ever passed to it. User-supplied values are
bound as statement parameters — never string-interpolated. There is no
general-purpose SQL endpoint anywhere in the app.
"""

from __future__ import annotations

import logging
from typing import Any, Protocol

from ..config import Settings
from ..genie.normalize import normalize_query_result
from ..models import QueryResult

logger = logging.getLogger("chicagopulse.warehouse")


class WarehouseProvider(Protocol):
    def run(self, sql: str, params: dict[str, Any] | None = None) -> QueryResult: ...


class DatabricksWarehouseProvider:
    """Executes governed queries via the SQL Statement Execution API."""

    def __init__(
        self,
        warehouse_id: str,
        settings: Settings,
        profile: str | None = None,
        host: str | None = None,
    ):
        from databricks.sdk import WorkspaceClient

        self.warehouse_id = warehouse_id
        self._settings = settings
        kwargs: dict[str, Any] = {}
        if profile:
            kwargs["profile"] = profile
        if host:
            kwargs["host"] = host
        self._w = WorkspaceClient(**kwargs)

    def run(self, sql: str, params: dict[str, Any] | None = None) -> QueryResult:
        from databricks.sdk.service.sql import StatementParameterListItem

        parameters = None
        if params:
            parameters = [
                StatementParameterListItem(name=name, value=None if value is None else str(value))
                for name, value in params.items()
            ]

        resp = self._w.statement_execution.execute_statement(
            warehouse_id=self.warehouse_id,
            statement=sql,
            parameters=parameters,
            wait_timeout="30s",
            row_limit=self._settings.max_result_rows,
        )
        result = normalize_query_result(resp, max_rows=self._settings.max_result_rows)
        return result or QueryResult()
