"""Data Health — freshness, coverage, and pipeline provenance."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Path

from ..config import Settings
from ..data import queries
from ..data.warehouse import WarehouseProvider
from ..deps import current_settings, get_pipeline_runner, get_warehouse
from ..models import DataHealthResponse, DatasetHealth, PipelineRunResponse
from ..pipeline.jobs import PipelineRunner, PipelineRunNotFound
from ..util import month_label, rows_as_dicts

logger = logging.getLogger("chicagopulse.api")
router = APIRouter()

_METRIC_EXPLANATION = (
    "ChicagoPulse aggregates raw City of Chicago records into monthly, "
    "Community-Area-level metrics in governed Unity Catalog tables. Only fully "
    "completed calendar months are reported, and month-over-month changes compare "
    "a completed month against the prior completed month. Metrics for a dataset "
    "are shown only when that dataset has data for the area and month; missing "
    "data is never treated as zero."
)
_SOURCE_NOTICE = (
    "Results depend on City of Chicago open datasets published via Socrata. "
    "Figures update as the city republishes source data and may be revised."
)

_ACTIVE_SOURCE_CATEGORIES = {
    "311 Service Requests": "Service Requests",
    "Business Licenses": "Community & Economic Development",
    "Building Permits": "Buildings",
    "Building Violations": "Buildings",
}

# Curated official City datasets that fit ChicagoPulse's neighborhood-level
# mission but are not ingested, modeled, or available to Genie today.
_FUTURE_SOURCES = (
    ("Food Inspections", "4ijn-s7e5", "Health & Human Services"),
    ("Crimes - 2001 to Present", "ijzp-q8t2", "Public Safety"),
    ("Traffic Crashes - Crashes", "85ca-t3if", "Transportation"),
    (
        "Affordable Rental Housing Developments",
        "s6ha-ppgi",
        "Community & Economic Development",
    ),
)


def _source_url(dataset_id: str) -> str:
    return f"https://data.cityofchicago.org/d/{dataset_id}"


@router.post("/data-health/pipeline-runs", response_model=PipelineRunResponse)
def trigger_pipeline(
    runner: PipelineRunner = Depends(get_pipeline_runner),
) -> PipelineRunResponse:
    """Start the one allowlisted refresh job, or return its active run."""
    try:
        return runner.trigger()
    except Exception:
        logger.exception("pipeline trigger failed")
        raise HTTPException(status_code=502, detail="Unable to start the pipeline run.")


@router.get("/data-health/pipeline-runs/{run_id}", response_model=PipelineRunResponse)
def pipeline_run_status(
    run_id: int = Path(gt=0),
    runner: PipelineRunner = Depends(get_pipeline_runner),
) -> PipelineRunResponse:
    try:
        return runner.get(run_id)
    except PipelineRunNotFound:
        raise HTTPException(status_code=404, detail="Pipeline run not found.")
    except Exception:
        logger.exception("pipeline run status failed")
        raise HTTPException(status_code=502, detail="Unable to load pipeline run status.")


@router.get("/data-health", response_model=DataHealthResponse)
def data_health(
    settings: Settings = Depends(current_settings),
    wh: WarehouseProvider = Depends(get_warehouse),
) -> DataHealthResponse:
    ns = settings.namespace

    # Freshness is authoritative; other lookups are best-effort so the page
    # always renders even if a supporting table is unavailable.
    freshness_rows: list[dict] = []
    try:
        sql, params = queries.data_freshness(ns)
        freshness_rows = rows_as_dicts(wh.run(sql, params))
    except Exception:
        logger.exception("data_freshness query failed")

    pipeline_status = "unknown"
    last_refresh = None
    try:
        sql, params = queries.latest_pipeline_run(ns)
        rows = rows_as_dicts(wh.run(sql, params))
        if rows:
            latest_run = rows[0]
            raw_status = str(latest_run.get("status") or "").upper()
            if raw_status == "SUCCESS":
                pipeline_status = "operational"
            elif raw_status in {"FAILED", "VALIDATION_FAILED"}:
                pipeline_status = "failed"
            elif raw_status:
                pipeline_status = raw_status.lower()
            if latest_run.get("last_success_at"):
                last_refresh = str(latest_run["last_success_at"])
    except Exception:
        logger.exception("latest_pipeline_run query failed")

    ingested: dict[str, str] = {}
    try:
        sql, params = queries.successful_dataset_runs(ns)
        for r in rows_as_dicts(wh.run(sql, params)):
            if r.get("dataset") and r.get("last_ingested_at"):
                ingested[str(r["dataset"])] = str(r["last_ingested_at"])
    except Exception:
        logger.exception("successful_dataset_runs query failed")

    latest_month = None
    try:
        sql, params = queries.latest_reporting_month(ns)
        rows = rows_as_dicts(wh.run(sql, params))
        if rows:
            latest_month = month_label(rows[0].get("metric_month"))
    except Exception:
        logger.exception("latest_reporting_month query failed")

    datasets = []
    for r in freshness_rows:
        name = str(r.get("dataset"))
        datasets.append(
            DatasetHealth(
                dataset=name,
                socrata_id=queries.SOCRATA_IDS.get(name),
                category=_ACTIVE_SOURCE_CATEGORIES.get(name),
                source_url=(
                    _source_url(queries.SOCRATA_IDS[name])
                    if name in queries.SOCRATA_IDS
                    else None
                ),
                usage_status="in_use",
                row_count=int(r["row_count"]) if r.get("row_count") is not None else None,
                min_date=str(r["min_date"]) if r.get("min_date") else None,
                max_date=str(r["max_date"]) if r.get("max_date") else None,
                last_ingested_at=ingested.get(name),
            )
        )

    datasets.extend(
        DatasetHealth(
            dataset=name,
            socrata_id=dataset_id,
            category=category,
            source_url=_source_url(dataset_id),
            usage_status="future_scope",
        )
        for name, dataset_id, category in _FUTURE_SOURCES
    )

    return DataHealthResponse(
        last_refresh_at=last_refresh,
        latest_reporting_month=latest_month,
        pipeline_status=pipeline_status,
        datasets=datasets,
        metric_explanation=_METRIC_EXPLANATION,
        source_notice=_SOURCE_NOTICE,
    )
