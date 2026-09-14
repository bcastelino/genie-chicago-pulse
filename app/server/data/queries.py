"""Allowlisted, parameterized read-only query templates over Gold tables.

These are the ONLY statements the server will run against the warehouse. Table
names come from trusted server config (never user input). Any user-supplied
value (community area numbers) is bound as a statement parameter. No dynamic
SQL is assembled from request bodies.
"""

from __future__ import annotations

from typing import Any

# Socrata dataset identifiers, from notebooks/01_bronze_ingestion.py. These are
# public, non-secret dataset ids used only for provenance display.
SOCRATA_IDS: dict[str, str] = {
    "311 Service Requests": "v6vf-nfxy",
    "Business Licenses": "r5kz-chrr",
    "Building Permits": "ydr8-5enu",
    "Building Violations": "22u3-xenr",
}

Query = tuple[str, dict[str, Any]]


def list_neighborhoods(ns: str) -> Query:
    return (
        f"""
        SELECT community_area, community_area_name
        FROM {ns}.gold_dim_community_area
        WHERE community_area BETWEEN 1 AND 77
        ORDER BY community_area_name
        """,
        {},
    )


def neighborhoods_geo(ns: str) -> Query:
    return (
        f"""
        SELECT community_area, community_area_name, geometry_geojson
        FROM {ns}.gold_dim_community_area
        WHERE community_area BETWEEN 1 AND 77
          AND geometry_geojson IS NOT NULL
        ORDER BY community_area
        """,
        {},
    )


def latest_pulse(ns: str, community_area: int) -> Query:
    return (
        f"""
        SELECT
            metric_month, community_area, community_area_name,
            service_request_count, previous_month_request_count, request_count_mom_pct,
            open_request_count, closed_request_count, avg_resolution_days,
            new_license_issues, previous_month_new_license_issues,
            permit_count, previous_month_permit_count, new_construction_permit_count,
            total_permit_fees,
            violation_count, previous_month_violation_count, open_violation_count,
            business_data_available, permit_data_available, violation_data_available
        FROM {ns}.gold_latest_neighborhood_pulse
        WHERE community_area = :ca
        """,
        {"ca": community_area},
    )


def trend_311(ns: str, community_area: int) -> Query:
    return (
        f"""
        WITH latest AS (
            SELECT MAX(metric_month) AS m
            FROM {ns}.gold_neighborhood_pulse
            WHERE is_complete_month = TRUE
        )
        SELECT metric_month, service_request_count
        FROM {ns}.gold_neighborhood_pulse
        WHERE community_area = :ca
          AND is_complete_month = TRUE
          AND metric_month BETWEEN ADD_MONTHS((SELECT m FROM latest), -11)
                               AND (SELECT m FROM latest)
        ORDER BY metric_month
        """,
        {"ca": community_area},
    )


def top_service_types(ns: str, community_area: int, limit: int = 10) -> Query:
    # limit is server-controlled (not user input); interpolation is safe.
    limit = max(1, min(int(limit), 25))
    return (
        f"""
        WITH latest AS (
            SELECT MAX(metric_month) AS m
            FROM {ns}.gold_service_type_trends
            WHERE is_complete_month = TRUE AND community_area = :ca
        )
        SELECT sr_type AS category, SUM(service_request_count) AS value
        FROM {ns}.gold_service_type_trends
        WHERE community_area = :ca
          AND is_complete_month = TRUE
          AND metric_month = (SELECT m FROM latest)
        GROUP BY sr_type
        ORDER BY value DESC
        LIMIT {limit}
        """,
        {"ca": community_area},
    )


def map_metric(ns: str) -> Query:
    """Latest-completed-month 311 volume for every Community Area (choropleth)."""
    return (
        f"""
        SELECT community_area, community_area_name, service_request_count
        FROM {ns}.gold_latest_neighborhood_pulse
        ORDER BY community_area
        """,
        {},
    )


def latest_reporting_month(ns: str) -> Query:
    return (
        f"""
        SELECT MAX(metric_month) AS metric_month
        FROM {ns}.gold_neighborhood_pulse
        WHERE is_complete_month = TRUE
        """,
        {},
    )


def compare_neighborhoods(ns: str, community_areas: list[int]) -> Query:
    # Bounded to <= 4 by the router; bind each as a named parameter.
    params: dict[str, Any] = {}
    markers: list[str] = []
    for i, ca in enumerate(community_areas):
        key = f"ca{i}"
        params[key] = ca
        markers.append(f":{key}")
    in_list = ", ".join(markers)
    return (
        f"""
        WITH latest AS (
            SELECT MAX(metric_month) AS m
            FROM {ns}.gold_neighborhood_pulse
            WHERE is_complete_month = TRUE
        )
        SELECT
            metric_month, community_area, community_area_name,
            service_request_count, request_count_mom_pct,
            open_request_count, avg_resolution_days,
            new_license_issues, permit_count, new_construction_permit_count,
            total_permit_fees, violation_count, open_violation_count,
            business_data_available, permit_data_available, violation_data_available
        FROM {ns}.gold_neighborhood_pulse
        WHERE is_complete_month = TRUE
          AND metric_month = (SELECT m FROM latest)
          AND community_area IN ({in_list})
        ORDER BY community_area_name
        """,
        params,
    )


def data_freshness(ns: str) -> Query:
    return (
        f"""
        SELECT dataset, row_count, min_date, max_date
        FROM {ns}.gold_data_freshness
        ORDER BY dataset
        """,
        {},
    )


def latest_pipeline_run(ns: str) -> Query:
    """Latest pipeline state plus the last end-to-end successful completion.

    Notebook 12 advances a run through ingestion, notebook 13 records transform
    completion, and notebook 14 alone writes SUCCESS after validation.  Data
    Health must therefore use this terminal run state rather than infer health
    from record ingestion timestamps.
    """
    return (
        f"""
        WITH ranked_runs AS (
            SELECT
                run_id, started_at, completed_at, status, message,
                ROW_NUMBER() OVER (ORDER BY started_at DESC) AS row_num
            FROM {ns}.etl_pipeline_runs
        ), last_success AS (
            SELECT MAX(completed_at) AS last_success_at
            FROM {ns}.etl_pipeline_runs
            WHERE status = 'SUCCESS'
        )
        SELECT
            r.run_id, r.started_at, r.completed_at, r.status, r.message,
            s.last_success_at
        FROM ranked_runs r
        CROSS JOIN last_success s
        WHERE r.row_num = 1
        """,
        {},
    )


def successful_dataset_runs(ns: str) -> Query:
    """Dataset ingestion completions belonging to the latest successful run."""
    return (
        f"""
        WITH latest_success AS (
            SELECT run_id
            FROM {ns}.etl_pipeline_runs
            WHERE status = 'SUCCESS'
            ORDER BY started_at DESC
            LIMIT 1
        ), ranked_dataset_runs AS (
            SELECT
                d.dataset, d.completed_at,
                ROW_NUMBER() OVER (
                    PARTITION BY d.dataset ORDER BY d.completed_at DESC
                ) AS row_num
            FROM {ns}.etl_dataset_runs d
            INNER JOIN latest_success p ON d.run_id = p.run_id
            WHERE d.status = 'SUCCESS'
        )
        SELECT
            CASE dataset
                WHEN '311' THEN '311 Service Requests'
                WHEN 'business_licenses' THEN 'Business Licenses'
                WHEN 'building_permits' THEN 'Building Permits'
                WHEN 'building_violations' THEN 'Building Violations'
                ELSE dataset
            END AS dataset,
            completed_at AS last_ingested_at
        FROM ranked_dataset_runs
        WHERE row_num = 1
        ORDER BY dataset
        """,
        {},
    )
