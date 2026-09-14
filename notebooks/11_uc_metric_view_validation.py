# Databricks notebook source
# MAGIC %md
# MAGIC # ChicagoPulse 11: UC Metric View Validation
# MAGIC
# MAGIC Run this before creating the Genie Agent.

# COMMAND ----------

CATALOG = spark.sql("SELECT current_catalog()").first()[0]
SCHEMA = "chicagopulse"

def exists(table):
    return spark.catalog.tableExists(f"{CATALOG}.{SCHEMA}.{table}")

required = [
    "mv_neighborhood_pulse",
    "mv_311_service_trends",
    "gold_neighborhood_pulse",
    "gold_311_service_semantic_base",
]

missing = [t for t in required if not exists(t)]
if missing:
    raise RuntimeError("Missing UC semantic objects: " + ", ".join(missing))

print("All required UC semantic objects exist.")

# COMMAND ----------

display(spark.sql(f'''
WITH latest AS (
  SELECT MAX(metric_month) AS metric_month
  FROM `{CATALOG}`.`{SCHEMA}`.`mv_neighborhood_pulse`
)
SELECT
  community_area_name,
  MEASURE(total_311_requests) AS total_311_requests,
  MEASURE(total_building_violations) AS building_violations,
  MEASURE(total_building_permits) AS building_permits,
  MEASURE(total_business_license_issues) AS business_license_issues
FROM `{CATALOG}`.`{SCHEMA}`.`mv_neighborhood_pulse`
WHERE metric_month = (SELECT metric_month FROM latest)
GROUP BY community_area_name
ORDER BY total_311_requests DESC
LIMIT 15
'''))

# COMMAND ----------

display(spark.sql(f'''
SELECT
  metric_month,
  community_area_name,
  MEASURE(current_month_311_requests) AS current_month_requests,
  MEASURE(previous_month_311_requests) AS previous_month_requests,
  MEASURE(request_mom_change_pct) AS request_mom_change_pct
FROM `{CATALOG}`.`{SCHEMA}`.`mv_neighborhood_pulse`
GROUP BY metric_month, community_area_name
ORDER BY metric_month DESC, request_mom_change_pct DESC
LIMIT 30
'''))

# COMMAND ----------

display(spark.sql(f'''
WITH latest AS (
  SELECT MAX(metric_month) AS metric_month
  FROM `{CATALOG}`.`{SCHEMA}`.`mv_311_service_trends`
)
SELECT
  community_area_name,
  service_request_type,
  MEASURE(total_311_requests) AS requests_311
FROM `{CATALOG}`.`{SCHEMA}`.`mv_311_service_trends`
WHERE metric_month = (SELECT metric_month FROM latest)
GROUP BY community_area_name, service_request_type
ORDER BY requests_311 DESC
LIMIT 30
'''))

# COMMAND ----------

display(spark.sql(f'''
WITH latest AS (
  SELECT MAX(metric_month) AS metric_month
  FROM `{CATALOG}`.`{SCHEMA}`.`mv_311_service_trends`
)
SELECT
  community_area_name,
  MEASURE(total_311_requests) AS requests_311,
  MEASURE(resolved_311_requests) AS resolved_requests,
  MEASURE(average_resolution_days) AS avg_resolution_days
FROM `{CATALOG}`.`{SCHEMA}`.`mv_311_service_trends`
WHERE metric_month = (SELECT metric_month FROM latest)
GROUP BY community_area_name
HAVING MEASURE(resolved_311_requests) >= 100
ORDER BY avg_resolution_days DESC
LIMIT 20
'''))

# COMMAND ----------

reconciliation = spark.sql(f'''
WITH latest AS (
  SELECT MAX(metric_month) AS metric_month
  FROM `{CATALOG}`.`{SCHEMA}`.`mv_neighborhood_pulse`
),
mv AS (
  SELECT MEASURE(total_311_requests) AS request_count
  FROM `{CATALOG}`.`{SCHEMA}`.`mv_neighborhood_pulse`
  WHERE metric_month = (SELECT metric_month FROM latest)
),
gold AS (
  SELECT SUM(service_request_count) AS request_count
  FROM `{CATALOG}`.`{SCHEMA}`.`gold_neighborhood_pulse`
  WHERE is_complete_month = TRUE
    AND metric_month = (SELECT metric_month FROM latest)
)
SELECT
  mv.request_count AS metric_view_count,
  gold.request_count AS gold_count,
  mv.request_count - gold.request_count AS difference
FROM mv CROSS JOIN gold
''')

display(reconciliation)

row = reconciliation.first()
assert row["difference"] == 0, f"Reconciliation failed. Difference: {row['difference']}"

print("Metric View reconciliation passed.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Genie sources after validation
# MAGIC
# MAGIC Add:
# MAGIC
# MAGIC `mv_neighborhood_pulse`
# MAGIC
# MAGIC `mv_311_service_trends`
# MAGIC
# MAGIC `gold_data_freshness`
# MAGIC
# MAGIC Routing guidance:
# MAGIC
# MAGIC Use `mv_neighborhood_pulse` for neighborhood comparisons and cross-dataset questions.
# MAGIC
# MAGIC Use `mv_311_service_trends` when the question asks about complaint categories, request types, detailed 311 trends, or resolution time.
# MAGIC
# MAGIC Use `gold_data_freshness` only for coverage and freshness questions.