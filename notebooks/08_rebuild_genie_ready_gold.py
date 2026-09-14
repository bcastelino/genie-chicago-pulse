# Databricks notebook source
# MAGIC %md
# MAGIC # ChicagoPulse 08: Rebuild Genie Ready Gold
# MAGIC
# MAGIC Run after notebooks 05, 06, and 07.
# MAGIC
# MAGIC This rebuilds the curated 311 Silver table from the full Bronze history and then rebuilds the final Gold layer.
# MAGIC
# MAGIC Month over month 311 percentages are intentionally NULL for the current incomplete month.

# COMMAND ----------

CATALOG=spark.sql("SELECT current_catalog()").first()[0]
SCHEMA="chicagopulse"

def exists(table):
    return spark.catalog.tableExists(f"{CATALOG}.{SCHEMA}.{table}")

def build(table,query):
    spark.sql(f'''
    CREATE OR REPLACE TABLE `{CATALOG}`.`{SCHEMA}`.`{table}` AS
    {query}
    ''')
    print(f"Built {CATALOG}.{SCHEMA}.{table}")

required=[
    "bronze_311_service_requests",
    "silver_business_licenses",
    "silver_building_permits",
    "silver_building_violations_enriched",
    "silver_community_area_boundaries",
]
missing=[t for t in required if not exists(t)]
if missing:
    raise RuntimeError("Missing required tables: "+", ".join(missing))

n311=spark.table(f"{CATALOG}.{SCHEMA}.bronze_311_service_requests").count()
print(f"Bronze 311 rows: {n311:,}")
if n311<=250_000:
    raise RuntimeError("Full 311 backfill has not been promoted yet. Finish notebook 05.")

# COMMAND ----------

build("silver_311_service_requests",f'''
SELECT
    sr_number,sr_type,sr_short_code,created_department,owner_department,status,origin,
    CAST(created_date AS TIMESTAMP) AS created_at,
    CAST(created_date AS DATE) AS created_date,
    CAST(last_modified_date AS TIMESTAMP) AS last_modified_at,
    CAST(closed_date AS TIMESTAMP) AS closed_at,
    CAST(closed_date AS DATE) AS closed_date,
    CASE WHEN closed_date IS NOT NULL
         THEN DATEDIFF(CAST(closed_date AS DATE),CAST(created_date AS DATE))
    END AS resolution_days,
    street_address,city,state,zip_code,
    CAST(ward AS INT) AS ward,
    CAST(community_area AS INT) AS community_area,
    CAST(latitude AS DOUBLE) AS latitude,
    CAST(longitude AS DOUBLE) AS longitude,
    _source_dataset_id,_ingested_at
FROM `{CATALOG}`.`{SCHEMA}`.`bronze_311_service_requests`
WHERE sr_number IS NOT NULL
''')

# COMMAND ----------

build("gold_dim_community_area",f'''
SELECT
    community_area,community_area_name,geometry_geojson,shape_area,shape_len
FROM `{CATALOG}`.`{SCHEMA}`.`silver_community_area_boundaries`
''')

build("gold_community_area_daily_metrics",f'''
SELECT
    created_date AS metric_date,
    community_area,
    COUNT(*) AS service_request_count,
    SUM(CASE WHEN UPPER(status) LIKE '%OPEN%' THEN 1 ELSE 0 END) AS open_request_count,
    SUM(CASE WHEN closed_at IS NOT NULL THEN 1 ELSE 0 END) AS closed_request_count,
    COUNT(DISTINCT sr_type) AS distinct_service_types,
    AVG(CASE WHEN resolution_days>=0 THEN resolution_days END) AS avg_resolution_days
FROM `{CATALOG}`.`{SCHEMA}`.`silver_311_service_requests`
WHERE community_area BETWEEN 1 AND 77
  AND created_date IS NOT NULL
GROUP BY created_date,community_area
''')

# COMMAND ----------

build("gold_community_area_monthly_metrics",f'''
WITH monthly AS (
    SELECT
        DATE_TRUNC('MONTH',created_date) AS metric_month,
        community_area,
        COUNT(*) AS service_request_count,
        SUM(CASE WHEN UPPER(status) LIKE '%OPEN%' THEN 1 ELSE 0 END) AS open_request_count,
        SUM(CASE WHEN closed_at IS NOT NULL THEN 1 ELSE 0 END) AS closed_request_count,
        COUNT(DISTINCT sr_type) AS distinct_service_types,
        AVG(CASE WHEN resolution_days>=0 THEN resolution_days END) AS avg_resolution_days
    FROM `{CATALOG}`.`{SCHEMA}`.`silver_311_service_requests`
    WHERE community_area BETWEEN 1 AND 77
      AND created_date IS NOT NULL
    GROUP BY DATE_TRUNC('MONTH',created_date),community_area
),
lagged AS (
    SELECT *,
        LAG(service_request_count) OVER (
            PARTITION BY community_area ORDER BY metric_month
        ) AS previous_month_request_count
    FROM monthly
)
SELECT *,
    metric_month<DATE_TRUNC('MONTH',CURRENT_DATE()) AS is_complete_month,
    CASE
        WHEN metric_month<DATE_TRUNC('MONTH',CURRENT_DATE())
         AND previous_month_request_count>0
        THEN ROUND(
            100.0*(service_request_count-previous_month_request_count)
            /previous_month_request_count,2
        )
    END AS request_count_mom_pct
FROM lagged
''')

build("gold_service_type_trends",f'''
SELECT
    DATE_TRUNC('MONTH',created_date) AS metric_month,
    community_area,
    sr_type,
    COUNT(*) AS service_request_count,
    DATE_TRUNC('MONTH',created_date)<DATE_TRUNC('MONTH',CURRENT_DATE()) AS is_complete_month
FROM `{CATALOG}`.`{SCHEMA}`.`silver_311_service_requests`
WHERE community_area BETWEEN 1 AND 77
  AND created_date IS NOT NULL
  AND sr_type IS NOT NULL
GROUP BY DATE_TRUNC('MONTH',created_date),community_area,sr_type
''')

# COMMAND ----------

build("gold_business_activity",f'''
WITH monthly AS (
    SELECT
        DATE_TRUNC('MONTH',license_start_date) AS metric_month,
        community_area,
        COUNT(*) AS license_records,
        SUM(CASE WHEN application_type='ISSUE' THEN 1 ELSE 0 END) AS new_license_issues,
        COUNT(DISTINCT account_number) AS distinct_business_accounts
    FROM `{CATALOG}`.`{SCHEMA}`.`silver_business_licenses`
    WHERE community_area BETWEEN 1 AND 77
      AND license_start_date IS NOT NULL
    GROUP BY DATE_TRUNC('MONTH',license_start_date),community_area
)
SELECT *,
    LAG(new_license_issues) OVER (
        PARTITION BY community_area ORDER BY metric_month
    ) AS previous_month_new_license_issues
FROM monthly
''')

build("gold_building_activity",f'''
WITH monthly AS (
    SELECT
        DATE_TRUNC('MONTH',issue_date) AS metric_month,
        community_area,
        COUNT(*) AS permit_count,
        SUM(CASE WHEN UPPER(permit_type) LIKE '%NEW CONSTRUCTION%' THEN 1 ELSE 0 END)
            AS new_construction_permit_count,
        SUM(COALESCE(total_fee,0)) AS total_permit_fees,
        AVG(processing_time_days) AS avg_processing_time_days
    FROM `{CATALOG}`.`{SCHEMA}`.`silver_building_permits`
    WHERE community_area BETWEEN 1 AND 77
      AND issue_date IS NOT NULL
    GROUP BY DATE_TRUNC('MONTH',issue_date),community_area
)
SELECT *,
    LAG(permit_count) OVER (
        PARTITION BY community_area ORDER BY metric_month
    ) AS previous_month_permit_count
FROM monthly
''')

# COMMAND ----------

build("gold_building_violation_activity",f'''
WITH monthly AS (
    SELECT
        DATE_TRUNC('MONTH',violation_date) AS metric_month,
        community_area,
        COUNT(*) AS violation_count,
        SUM(CASE WHEN UPPER(violation_status)='OPEN' THEN 1 ELSE 0 END)
            AS open_violation_count,
        COUNT(DISTINCT violation_code) AS distinct_violation_codes
    FROM `{CATALOG}`.`{SCHEMA}`.`silver_building_violations_enriched`
    WHERE community_area BETWEEN 1 AND 77
      AND violation_date IS NOT NULL
      AND geography_match_status='MATCHED'
    GROUP BY DATE_TRUNC('MONTH',violation_date),community_area
)
SELECT *,
    LAG(violation_count) OVER (
        PARTITION BY community_area ORDER BY metric_month
    ) AS previous_month_violation_count
FROM monthly
''')

# COMMAND ----------

build("gold_neighborhood_pulse",f'''
SELECT
    r.metric_month,
    r.community_area,
    d.community_area_name,
    r.is_complete_month,

    r.service_request_count,
    r.previous_month_request_count,
    r.request_count_mom_pct,
    r.open_request_count,
    r.closed_request_count,
    r.distinct_service_types,
    r.avg_resolution_days,

    b.license_records,
    b.new_license_issues,
    b.previous_month_new_license_issues,
    b.distinct_business_accounts,

    p.permit_count,
    p.previous_month_permit_count,
    p.new_construction_permit_count,
    p.total_permit_fees,
    p.avg_processing_time_days,

    v.violation_count,
    v.previous_month_violation_count,
    v.open_violation_count,
    v.distinct_violation_codes,

    b.metric_month IS NOT NULL AS business_data_available,
    p.metric_month IS NOT NULL AS permit_data_available,
    v.metric_month IS NOT NULL AS violation_data_available,

    CASE WHEN r.is_complete_month
          AND r.service_request_count>=50
          AND r.request_count_mom_pct>=20
         THEN TRUE ELSE FALSE
    END AS complaints_rising_flag,

    CASE WHEN r.is_complete_month
          AND b.previous_month_new_license_issues>0
          AND b.new_license_issues<b.previous_month_new_license_issues
         THEN TRUE ELSE FALSE
    END AS new_business_activity_declining_flag,

    CASE WHEN r.is_complete_month
          AND v.previous_month_violation_count>0
          AND v.violation_count>v.previous_month_violation_count
         THEN TRUE ELSE FALSE
    END AS building_violations_rising_flag,

    CASE WHEN r.is_complete_month
          AND p.previous_month_permit_count>0
          AND p.permit_count<p.previous_month_permit_count
         THEN TRUE ELSE FALSE
    END AS permit_activity_declining_flag

FROM `{CATALOG}`.`{SCHEMA}`.`gold_community_area_monthly_metrics` r
JOIN `{CATALOG}`.`{SCHEMA}`.`gold_dim_community_area` d
  ON r.community_area=d.community_area
LEFT JOIN `{CATALOG}`.`{SCHEMA}`.`gold_business_activity` b
  ON r.metric_month=b.metric_month AND r.community_area=b.community_area
LEFT JOIN `{CATALOG}`.`{SCHEMA}`.`gold_building_activity` p
  ON r.metric_month=p.metric_month AND r.community_area=p.community_area
LEFT JOIN `{CATALOG}`.`{SCHEMA}`.`gold_building_violation_activity` v
  ON r.metric_month=v.metric_month AND r.community_area=v.community_area
''')

# COMMAND ----------

build("gold_latest_neighborhood_pulse",f'''
SELECT *
FROM `{CATALOG}`.`{SCHEMA}`.`gold_neighborhood_pulse`
WHERE is_complete_month=TRUE
  AND metric_month=(
      SELECT MAX(metric_month)
      FROM `{CATALOG}`.`{SCHEMA}`.`gold_neighborhood_pulse`
      WHERE is_complete_month=TRUE
  )
''')

display(spark.sql(f'''
SELECT metric_month,COUNT(*) AS community_areas
FROM `{CATALOG}`.`{SCHEMA}`.`gold_latest_neighborhood_pulse`
GROUP BY metric_month
'''))