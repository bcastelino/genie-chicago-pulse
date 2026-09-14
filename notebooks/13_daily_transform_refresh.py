# Databricks notebook source
# MAGIC %md
# MAGIC # ChicagoPulse 13: Daily Transform Refresh
# MAGIC
# MAGIC Runs after Notebook 12.
# MAGIC
# MAGIC Refreshes changed Silver rows, re-enriches changed Building Violations, updates affected 311 aggregates,
# MAGIC rebuilds the small secondary Gold tables, rebuilds Neighborhood Pulse, and refreshes data freshness.
# MAGIC
# MAGIC The Metric View definitions do not need to be recreated.

# COMMAND ----------

CATALOG=spark.sql("SELECT current_catalog()").first()[0]
SCHEMA="chicagopulse"

def fq(t):
    return f"`{CATALOG}`.`{SCHEMA}`.`{t}`"

def exists(t):
    return spark.catalog.tableExists(f"{CATALOG}.{SCHEMA}.{t}")

run=spark.table(f"{CATALOG}.{SCHEMA}.etl_current_run").first()
RUN_ID=run["run_id"]

status=spark.sql(f'''
SELECT status FROM {fq("etl_pipeline_runs")}
WHERE run_id='{RUN_ID}'
ORDER BY started_at DESC LIMIT 1
''').first()["status"]

if status!="INGESTION_COMPLETE":
    raise RuntimeError(f"Run {RUN_ID} is not ready. Status={status}")

print("Transforming run:",RUN_ID)

# COMMAND ----------

def stage_has_rows(t):
    return exists(t) and spark.table(f"{CATALOG}.{SCHEMA}.{t}").limit(1).count()>0

def merge_typed(target,query,pk):
    temp=f"_tmp_{target}_{RUN_ID[:8]}"
    spark.sql(f"CREATE OR REPLACE TEMP VIEW `{temp}` AS {query}")

    target_cols=[f.name for f in spark.table(f"{CATALOG}.{SCHEMA}.{target}").schema.fields]
    source_cols=spark.table(temp).columns
    shared=[c for c in source_cols if c in target_cols]

    updates=",\n".join([f"t.`{c}`=s.`{c}`" for c in shared])
    cols=", ".join([f"`{c}`" for c in shared])
    vals=", ".join([f"s.`{c}`" for c in shared])

    spark.sql(f'''
    MERGE INTO {fq(target)} t
    USING `{temp}` s
    ON t.`{pk}`=s.`{pk}`
    WHEN MATCHED THEN UPDATE SET {updates}
    WHEN NOT MATCHED THEN INSERT ({cols}) VALUES ({vals})
    ''')

# COMMAND ----------

if stage_has_rows("stage_daily_311_service_requests"):
    merge_typed("silver_311_service_requests",f'''
    SELECT
      sr_number,sr_type,sr_short_code,created_department,owner_department,status,origin,
      TRY_CAST(created_date AS TIMESTAMP) AS created_at,
      TRY_CAST(created_date AS DATE) AS created_date,
      TRY_CAST(last_modified_date AS TIMESTAMP) AS last_modified_at,
      TRY_CAST(closed_date AS TIMESTAMP) AS closed_at,
      TRY_CAST(closed_date AS DATE) AS closed_date,
      CASE WHEN TRY_CAST(closed_date AS DATE) IS NOT NULL
           THEN DATEDIFF(TRY_CAST(closed_date AS DATE),TRY_CAST(created_date AS DATE))
      END AS resolution_days,
      street_address,city,state,zip_code,
      TRY_CAST(ward AS INT) AS ward,
      TRY_CAST(community_area AS INT) AS community_area,
      TRY_CAST(latitude AS DOUBLE) AS latitude,
      TRY_CAST(longitude AS DOUBLE) AS longitude,
      _source_dataset_id,
      TRY_CAST(_ingested_at AS TIMESTAMP) AS _ingested_at
    FROM {fq("stage_daily_311_service_requests")}
    WHERE sr_number IS NOT NULL
    ''',"sr_number")
    print("Silver 311 refreshed")

if stage_has_rows("stage_daily_business_licenses"):
    merge_typed("silver_business_licenses",f'''
    SELECT
      id,TRY_CAST(license_id AS BIGINT) AS license_id,
      TRY_CAST(account_number AS BIGINT) AS account_number,
      legal_name,doing_business_as_name,address,
      TRY_CAST(ward AS INT) AS ward,
      TRY_CAST(community_area AS INT) AS community_area,
      community_area_name,neighborhood,license_description,application_type,
      TRY_CAST(license_start_date AS DATE) AS license_start_date,
      CASE WHEN expiration_date LIKE '9999-%' THEN NULL
           ELSE TRY_CAST(expiration_date AS DATE) END AS expiration_date,
      license_status,
      TRY_CAST(license_status_change_date AS DATE) AS license_status_change_date,
      TRY_CAST(latitude AS DOUBLE) AS latitude,
      TRY_CAST(longitude AS DOUBLE) AS longitude,
      _source_dataset_id,
      TRY_CAST(_ingested_at AS TIMESTAMP) AS _ingested_at
    FROM {fq("stage_daily_business_licenses")}
    WHERE id IS NOT NULL
    ''',"id")
    print("Silver business licenses refreshed")

if stage_has_rows("stage_daily_building_permits"):
    merge_typed("silver_building_permits",f'''
    SELECT
      id,permit_ AS permit_number,permit_status,permit_milestone,permit_type,
      TRY_CAST(application_start_date AS DATE) AS application_start_date,
      TRY_CAST(issue_date AS DATE) AS issue_date,
      TRY_CAST(processing_time AS INT) AS processing_time_days,
      CONCAT_WS(' ',street_number,street_direction,street_name) AS address,
      work_type,work_description,
      TRY_CAST(total_fee AS DOUBLE) AS total_fee,
      TRY_CAST(community_area AS INT) AS community_area,
      TRY_CAST(ward AS INT) AS ward,
      TRY_CAST(latitude AS DOUBLE) AS latitude,
      TRY_CAST(longitude AS DOUBLE) AS longitude,
      _source_dataset_id,
      TRY_CAST(_ingested_at AS TIMESTAMP) AS _ingested_at
    FROM {fq("stage_daily_building_permits")}
    WHERE id IS NOT NULL
    ''',"id")
    print("Silver building permits refreshed")

# COMMAND ----------

if stage_has_rows("stage_daily_building_violations"):
    merge_typed("silver_building_violations",f'''
    SELECT
      id,
      TRY_CAST(violation_date AS DATE) AS violation_date,
      violation_code,UPPER(violation_status) AS violation_status,
      TRY_CAST(violation_status_date AS DATE) AS violation_status_date,
      violation_description,violation_inspector_comments,
      inspection_category,department_bureau,address,
      TRY_CAST(latitude AS DOUBLE) AS latitude,
      TRY_CAST(longitude AS DOUBLE) AS longitude,
      _source_dataset_id,
      TRY_CAST(_ingested_at AS TIMESTAMP) AS _ingested_at
    FROM {fq("stage_daily_building_violations")}
    WHERE id IS NOT NULL
    ''',"id")

    spark.sql(f'''
    CREATE OR REPLACE TEMP VIEW `_changed_violation_enrichment` AS
    SELECT
      v.*,
      c.community_area,
      c.community_area_name,
      CASE
        WHEN v.latitude IS NULL OR v.longitude IS NULL THEN 'MISSING_COORDINATES'
        WHEN c.community_area IS NOT NULL THEN 'MATCHED'
        ELSE 'OUTSIDE_OR_UNMATCHED'
      END AS geography_match_status
    FROM {fq("silver_building_violations")} v
    INNER JOIN {fq("stage_daily_building_violations")} s ON v.id=s.id
    LEFT JOIN {fq("silver_community_area_boundaries")} c
      ON v.latitude IS NOT NULL
     AND v.longitude IS NOT NULL
     AND ST_COVERS(
          ST_GEOMFROMGEOJSON(c.geometry_geojson),
          ST_POINT(v.longitude,v.latitude,4326)
     )
    ''')

    spark.sql(f'''
    MERGE INTO {fq("silver_building_violations_enriched")} t
    USING `_changed_violation_enrichment` s
    ON t.id=s.id
    WHEN MATCHED THEN UPDATE SET *
    WHEN NOT MATCHED THEN INSERT *
    ''')
    print("Silver violations refreshed and re-enriched")

# COMMAND ----------

affected=[
    r["metric_month"]
    for r in spark.sql(f'''
      SELECT DISTINCT metric_month
      FROM {fq("etl_affected_periods")}
      WHERE run_id='{RUN_ID}'
        AND dataset='bronze_311_service_requests'
        AND metric_month IS NOT NULL
      ORDER BY metric_month
    ''').collect()
]

print("Affected 311 months:",affected)

if not exists("gold_311_monthly_base"):
    spark.sql(f'''
    CREATE TABLE {fq("gold_311_monthly_base")} AS
    SELECT
      metric_month,community_area,service_request_count,
      open_request_count,closed_request_count,
      distinct_service_types,avg_resolution_days
    FROM {fq("gold_community_area_monthly_metrics")}
    ''')
    print("Initialized gold_311_monthly_base")

# COMMAND ----------

if affected:
    months=", ".join([f"DATE('{m.isoformat()}')" for m in affected])

    spark.sql(f'''
    DELETE FROM {fq("gold_311_monthly_base")}
    WHERE CAST(metric_month AS DATE) IN ({months})
    ''')

    spark.sql(f'''
    INSERT INTO {fq("gold_311_monthly_base")}
    SELECT
      DATE_TRUNC('MONTH',created_date) AS metric_month,
      community_area,
      COUNT(*) AS service_request_count,
      SUM(CASE WHEN UPPER(status) LIKE '%OPEN%' THEN 1 ELSE 0 END) AS open_request_count,
      SUM(CASE WHEN closed_at IS NOT NULL THEN 1 ELSE 0 END) AS closed_request_count,
      COUNT(DISTINCT sr_type) AS distinct_service_types,
      AVG(CASE WHEN resolution_days>=0 THEN resolution_days END) AS avg_resolution_days
    FROM {fq("silver_311_service_requests")}
    WHERE community_area BETWEEN 1 AND 77
      AND created_date IS NOT NULL
      AND CAST(DATE_TRUNC('MONTH',created_date) AS DATE) IN ({months})
    GROUP BY DATE_TRUNC('MONTH',created_date),community_area
    ''')

    spark.sql(f'''
    DELETE FROM {fq("gold_311_service_semantic_base")}
    WHERE CAST(metric_month AS DATE) IN ({months})
    ''')

    spark.sql(f'''
    INSERT INTO {fq("gold_311_service_semantic_base")}
    SELECT
      DATE_TRUNC('MONTH',created_date) AS metric_month,
      community_area,
      sr_type AS service_request_type,
      COUNT(*) AS service_request_count,
      SUM(CASE WHEN UPPER(status) LIKE '%OPEN%' THEN 1 ELSE 0 END) AS open_request_count,
      SUM(CASE WHEN closed_at IS NOT NULL THEN 1 ELSE 0 END) AS closed_request_count,
      SUM(CASE WHEN resolution_days>=0 THEN 1 ELSE 0 END) AS resolved_request_count,
      SUM(CASE WHEN resolution_days>=0 THEN resolution_days ELSE 0 END) AS total_resolution_days
    FROM {fq("silver_311_service_requests")}
    WHERE community_area BETWEEN 1 AND 77
      AND created_date IS NOT NULL
      AND sr_type IS NOT NULL
      AND CAST(DATE_TRUNC('MONTH',created_date) AS DATE) IN ({months})
    GROUP BY DATE_TRUNC('MONTH',created_date),community_area,sr_type
    ''')

    spark.sql(f'''
    DELETE FROM {fq("gold_community_area_daily_metrics")}
    WHERE CAST(DATE_TRUNC('MONTH',metric_date) AS DATE) IN ({months})
    ''')

    spark.sql(f'''
    INSERT INTO {fq("gold_community_area_daily_metrics")}
    SELECT
      created_date AS metric_date,
      community_area,
      COUNT(*) AS service_request_count,
      SUM(CASE WHEN UPPER(status) LIKE '%OPEN%' THEN 1 ELSE 0 END) AS open_request_count,
      SUM(CASE WHEN closed_at IS NOT NULL THEN 1 ELSE 0 END) AS closed_request_count,
      COUNT(DISTINCT sr_type) AS distinct_service_types,
      AVG(CASE WHEN resolution_days>=0 THEN resolution_days END) AS avg_resolution_days
    FROM {fq("silver_311_service_requests")}
    WHERE community_area BETWEEN 1 AND 77
      AND created_date IS NOT NULL
      AND CAST(DATE_TRUNC('MONTH',created_date) AS DATE) IN ({months})
    GROUP BY created_date,community_area
    ''')
    print("Affected 311 aggregates refreshed")
else:
    print("No 311 aggregate refresh required")

# COMMAND ----------

spark.sql(f'''
CREATE OR REPLACE TABLE {fq("gold_community_area_monthly_metrics")} AS
WITH lagged AS (
  SELECT *,
    LAG(service_request_count) OVER (
      PARTITION BY community_area ORDER BY metric_month
    ) AS previous_month_request_count
  FROM {fq("gold_311_monthly_base")}
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

spark.sql(f'''
CREATE OR REPLACE TABLE {fq("gold_service_type_trends")} AS
SELECT
  metric_month,community_area,
  service_request_type AS sr_type,
  service_request_count,
  metric_month<DATE_TRUNC('MONTH',CURRENT_DATE()) AS is_complete_month
FROM {fq("gold_311_service_semantic_base")}
''')

# COMMAND ----------

spark.sql(f'''
CREATE OR REPLACE TABLE {fq("gold_business_activity")} AS
WITH monthly AS (
  SELECT
    DATE_TRUNC('MONTH',license_start_date) AS metric_month,
    community_area,
    COUNT(*) AS license_records,
    SUM(CASE WHEN application_type='ISSUE' THEN 1 ELSE 0 END) AS new_license_issues,
    COUNT(DISTINCT account_number) AS distinct_business_accounts
  FROM {fq("silver_business_licenses")}
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

spark.sql(f'''
CREATE OR REPLACE TABLE {fq("gold_building_activity")} AS
WITH monthly AS (
  SELECT
    DATE_TRUNC('MONTH',issue_date) AS metric_month,
    community_area,
    COUNT(*) AS permit_count,
    SUM(CASE WHEN UPPER(permit_type) LIKE '%NEW CONSTRUCTION%' THEN 1 ELSE 0 END)
      AS new_construction_permit_count,
    SUM(COALESCE(total_fee,0)) AS total_permit_fees,
    AVG(processing_time_days) AS avg_processing_time_days
  FROM {fq("silver_building_permits")}
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

spark.sql(f'''
CREATE OR REPLACE TABLE {fq("gold_building_violation_activity")} AS
WITH monthly AS (
  SELECT
    DATE_TRUNC('MONTH',violation_date) AS metric_month,
    community_area,
    COUNT(*) AS violation_count,
    SUM(CASE WHEN UPPER(violation_status)='OPEN' THEN 1 ELSE 0 END) AS open_violation_count,
    COUNT(DISTINCT violation_code) AS distinct_violation_codes
  FROM {fq("silver_building_violations_enriched")}
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

spark.sql(f'''
CREATE OR REPLACE TABLE {fq("gold_neighborhood_pulse")} AS
SELECT
  r.metric_month,r.community_area,d.community_area_name,r.is_complete_month,
  r.service_request_count,r.previous_month_request_count,r.request_count_mom_pct,
  r.open_request_count,r.closed_request_count,r.distinct_service_types,r.avg_resolution_days,
  b.license_records,b.new_license_issues,b.previous_month_new_license_issues,b.distinct_business_accounts,
  p.permit_count,p.previous_month_permit_count,p.new_construction_permit_count,
  p.total_permit_fees,p.avg_processing_time_days,
  v.violation_count,v.previous_month_violation_count,v.open_violation_count,v.distinct_violation_codes,
  b.metric_month IS NOT NULL AS business_data_available,
  p.metric_month IS NOT NULL AS permit_data_available,
  v.metric_month IS NOT NULL AS violation_data_available,
  CASE WHEN r.is_complete_month AND r.service_request_count>=50 AND r.request_count_mom_pct>=20
       THEN TRUE ELSE FALSE END AS complaints_rising_flag,
  CASE WHEN r.is_complete_month AND b.previous_month_new_license_issues>0
         AND b.new_license_issues<b.previous_month_new_license_issues
       THEN TRUE ELSE FALSE END AS new_business_activity_declining_flag,
  CASE WHEN r.is_complete_month AND v.previous_month_violation_count>0
         AND v.violation_count>v.previous_month_violation_count
       THEN TRUE ELSE FALSE END AS building_violations_rising_flag,
  CASE WHEN r.is_complete_month AND p.previous_month_permit_count>0
         AND p.permit_count<p.previous_month_permit_count
       THEN TRUE ELSE FALSE END AS permit_activity_declining_flag
FROM {fq("gold_community_area_monthly_metrics")} r
JOIN {fq("gold_dim_community_area")} d
  ON r.community_area=d.community_area
LEFT JOIN {fq("gold_business_activity")} b
  ON r.metric_month=b.metric_month AND r.community_area=b.community_area
LEFT JOIN {fq("gold_building_activity")} p
  ON r.metric_month=p.metric_month AND r.community_area=p.community_area
LEFT JOIN {fq("gold_building_violation_activity")} v
  ON r.metric_month=v.metric_month AND r.community_area=v.community_area
''')

spark.sql(f'''
CREATE OR REPLACE TABLE {fq("gold_latest_neighborhood_pulse")} AS
SELECT *
FROM {fq("gold_neighborhood_pulse")}
WHERE is_complete_month=TRUE
  AND metric_month=(
    SELECT MAX(metric_month)
    FROM {fq("gold_neighborhood_pulse")}
    WHERE is_complete_month=TRUE
  )
''')

# COMMAND ----------

spark.sql(f'''
CREATE OR REPLACE TABLE {fq("gold_data_freshness")} AS
SELECT '311 Service Requests' AS dataset,COUNT(*) AS row_count,
       MIN(created_date) AS min_date,MAX(created_date) AS max_date,
       MAX(_ingested_at) AS last_ingested_at
FROM {fq("silver_311_service_requests")}
UNION ALL
SELECT 'Business Licenses',COUNT(*),MIN(license_start_date),MAX(license_start_date),MAX(_ingested_at)
FROM {fq("silver_business_licenses")}
UNION ALL
SELECT 'Building Permits',COUNT(*),MIN(issue_date),MAX(issue_date),MAX(_ingested_at)
FROM {fq("silver_building_permits")}
UNION ALL
SELECT 'Building Violations',COUNT(*),MIN(violation_date),MAX(violation_date),MAX(_ingested_at)
FROM {fq("silver_building_violations_enriched")}
''')

spark.sql(f'''
UPDATE {fq("etl_pipeline_runs")}
SET status='TRANSFORM_COMPLETE',
    message='Silver and Gold refresh completed'
WHERE run_id='{RUN_ID}' AND status='INGESTION_COMPLETE'
''')

display(spark.table(f"{CATALOG}.{SCHEMA}.gold_data_freshness"))