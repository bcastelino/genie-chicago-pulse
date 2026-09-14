"""Neighborhood Pulse — governed, read-only metric endpoints."""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from ..config import Settings
from ..data import queries
from ..data.warehouse import WarehouseProvider
from ..deps import current_settings, get_warehouse
from ..models import (
    CategoryCount,
    ComparisonResponse,
    MapMetricPoint,
    MapMetricResponse,
    MetricValue,
    Neighborhood,
    NeighborhoodPulse,
    TrendPoint,
)
from ..util import month_key, month_label, pct_change, rows_as_dicts, to_float

logger = logging.getLogger("chicagopulse.api")
router = APIRouter(prefix="/neighborhoods")

_VALID_AREAS = set(range(1, 78))


def _metrics_from_row(row: dict[str, Any]) -> list[MetricValue]:
    """Map a pulse row to labeled metrics, honoring *_data_available flags."""
    biz_ok = bool(row.get("business_data_available", True))
    permit_ok = bool(row.get("permit_data_available", True))
    viol_ok = bool(row.get("violation_data_available", True))

    req = to_float(row.get("service_request_count"))
    prev_req = to_float(row.get("previous_month_request_count"))
    permits = to_float(row.get("permit_count"))
    prev_permits = to_float(row.get("previous_month_permit_count"))
    viol = to_float(row.get("violation_count"))
    prev_viol = to_float(row.get("previous_month_violation_count"))
    biz = to_float(row.get("new_license_issues"))
    prev_biz = to_float(row.get("previous_month_new_license_issues"))

    return [
        MetricValue(
            key="total_311_requests", label="311 Requests", value=req,
            previous_value=prev_req,
            mom_change_pct=to_float(row.get("request_count_mom_pct")),
            unit="count", available=True,
        ),
        MetricValue(
            key="open_311_requests", label="Open 311 Requests",
            value=to_float(row.get("open_request_count")), unit="count", available=True,
        ),
        MetricValue(
            key="avg_resolution_days", label="Avg. Resolution",
            value=to_float(row.get("avg_resolution_days")), unit="days", available=True,
        ),
        MetricValue(
            key="business_license_issues", label="Business Licenses",
            value=biz if biz_ok else None, previous_value=prev_biz if biz_ok else None,
            mom_change_pct=pct_change(biz, prev_biz) if biz_ok else None,
            unit="count", available=biz_ok,
        ),
        MetricValue(
            key="building_permits", label="Building Permits",
            value=permits if permit_ok else None,
            previous_value=prev_permits if permit_ok else None,
            mom_change_pct=pct_change(permits, prev_permits) if permit_ok else None,
            unit="count", available=permit_ok,
        ),
        MetricValue(
            key="building_violations", label="Building Violations",
            value=viol if viol_ok else None, previous_value=prev_viol if viol_ok else None,
            mom_change_pct=pct_change(viol, prev_viol) if viol_ok else None,
            unit="count", available=viol_ok,
        ),
    ]


@router.get("", response_model=list[Neighborhood])
def list_neighborhoods(
    settings: Settings = Depends(current_settings),
    wh: WarehouseProvider = Depends(get_warehouse),
) -> list[Neighborhood]:
    sql, params = queries.list_neighborhoods(settings.namespace)
    try:
        result = wh.run(sql, params)
    except Exception:
        logger.exception("list_neighborhoods query failed")
        raise HTTPException(status_code=502, detail="Unable to load neighborhoods.")
    out = []
    for row in rows_as_dicts(result):
        ca = row.get("community_area")
        name = row.get("community_area_name")
        if ca is None or name is None:
            continue
        out.append(Neighborhood(community_area=int(ca), community_area_name=str(name)))
    return out


@router.get("/geo")
def neighborhoods_geo(
    settings: Settings = Depends(current_settings),
    wh: WarehouseProvider = Depends(get_warehouse),
) -> dict[str, Any]:
    sql, params = queries.neighborhoods_geo(settings.namespace)
    try:
        result = wh.run(sql, params)
    except Exception:
        logger.exception("neighborhoods_geo query failed")
        raise HTTPException(status_code=502, detail="Unable to load boundaries.")
    features = []
    for row in rows_as_dicts(result):
        raw = row.get("geometry_geojson")
        if not raw:
            continue
        try:
            geometry = json.loads(raw)
        except (TypeError, ValueError):
            continue
        features.append(
            {
                "type": "Feature",
                "properties": {
                    "community_area": int(row["community_area"]),
                    "community_area_name": row.get("community_area_name"),
                },
                "geometry": geometry,
            }
        )
    return {"type": "FeatureCollection", "features": features}


@router.get("/map", response_model=MapMetricResponse)
def map_metric(
    settings: Settings = Depends(current_settings),
    wh: WarehouseProvider = Depends(get_warehouse),
) -> MapMetricResponse:
    sql, params = queries.map_metric(settings.namespace)
    try:
        result = wh.run(sql, params)
    except Exception:
        logger.exception("map_metric query failed")
        raise HTTPException(status_code=502, detail="Unable to load map data.")
    rows = rows_as_dicts(result)
    metric_month = rows[0].get("metric_month") if rows and "metric_month" in rows[0] else None
    values = [
        MapMetricPoint(
            community_area=int(r["community_area"]),
            community_area_name=str(r.get("community_area_name")),
            value=to_float(r.get("service_request_count")),
        )
        for r in rows
        if r.get("community_area") is not None
    ]
    return MapMetricResponse(
        metric_month=None,
        reporting_period_label=month_label(metric_month),
        metric_label="311 Requests",
        values=values,
    )


@router.get("/compare", response_model=ComparisonResponse)
def compare_neighborhoods(
    areas: str = Query(..., description="Comma-separated community area numbers (max 4)."),
    settings: Settings = Depends(current_settings),
    wh: WarehouseProvider = Depends(get_warehouse),
) -> ComparisonResponse:
    parsed: list[int] = []
    for token in areas.split(","):
        token = token.strip()
        if not token:
            continue
        if not token.isdigit() or int(token) not in _VALID_AREAS:
            raise HTTPException(status_code=422, detail=f"Invalid community area: {token}")
        if int(token) not in parsed:
            parsed.append(int(token))
    if not parsed:
        raise HTTPException(status_code=422, detail="At least one community area is required.")
    if len(parsed) > 4:
        raise HTTPException(status_code=422, detail="Compare at most 4 neighborhoods.")

    sql, params = queries.compare_neighborhoods(settings.namespace, parsed)
    try:
        result = wh.run(sql, params)
    except Exception:
        logger.exception("compare query failed")
        raise HTTPException(status_code=502, detail="Unable to compare neighborhoods.")

    rows = rows_as_dicts(result)
    metric_month = rows[0].get("metric_month") if rows else None
    neighborhoods = [
        NeighborhoodPulse(
            community_area=int(r["community_area"]),
            community_area_name=str(r.get("community_area_name")),
            metric_month=month_key(r.get("metric_month")),
            reporting_period_label=month_label(r.get("metric_month")),
            metrics=_metrics_from_row(r),
        )
        for r in rows
    ]
    return ComparisonResponse(
        metric_month=month_key(metric_month),
        reporting_period_label=month_label(metric_month),
        metric_keys=_metrics_from_row(rows[0]) if rows else [],
        neighborhoods=neighborhoods,
    )


@router.get("/{community_area}/pulse", response_model=NeighborhoodPulse)
def neighborhood_pulse(
    community_area: int,
    settings: Settings = Depends(current_settings),
    wh: WarehouseProvider = Depends(get_warehouse),
) -> NeighborhoodPulse:
    if community_area not in _VALID_AREAS:
        raise HTTPException(status_code=422, detail="Invalid community area.")

    ns = settings.namespace
    try:
        pulse_sql, pulse_params = queries.latest_pulse(ns, community_area)
        pulse_result = wh.run(pulse_sql, pulse_params)
        trend_sql, trend_params = queries.trend_311(ns, community_area)
        trend_result = wh.run(trend_sql, trend_params)
        types_sql, types_params = queries.top_service_types(ns, community_area)
        types_result = wh.run(types_sql, types_params)
    except Exception:
        logger.exception("neighborhood_pulse query failed")
        raise HTTPException(status_code=502, detail="Unable to load neighborhood data.")

    pulse_rows = rows_as_dicts(pulse_result)
    if not pulse_rows:
        raise HTTPException(status_code=404, detail="No data for this neighborhood yet.")
    row = pulse_rows[0]

    trend = [
        TrendPoint(
            metric_month=month_key(r.get("metric_month")) or "",
            value=to_float(r.get("service_request_count")),
        )
        for r in rows_as_dicts(trend_result)
    ]
    top_types = [
        CategoryCount(category=str(r.get("category")), value=to_float(r.get("value")) or 0.0)
        for r in rows_as_dicts(types_result)
    ]

    return NeighborhoodPulse(
        community_area=community_area,
        community_area_name=str(row.get("community_area_name")),
        metric_month=month_key(row.get("metric_month")),
        reporting_period_label=month_label(row.get("metric_month")),
        metrics=_metrics_from_row(row),
        trend_311=trend,
        top_service_types=top_types,
    )
