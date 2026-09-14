# Databricks notebook source
# MAGIC %md
# MAGIC # ChicagoPulse 10: UC Semantic Base and Metric Views
# MAGIC
# MAGIC This notebook finishes the Unity Catalog semantic layer before Genie.
# MAGIC
# MAGIC It creates:
# MAGIC
# MAGIC 1. `gold_311_service_semantic_base`
# MAGIC 2. `mv_neighborhood_pulse`
# MAGIC 3. `mv_311_service_trends`
# MAGIC
# MAGIC The 311 semantic base stores additive components so resolution-time metrics remain mathematically correct when users regroup the data.

# COMMAND ----------

CATALOG = spark.sql("SELECT current_catalog()").first()[0]
SCHEMA = "chicagopulse"

def exists(table):
    return spark.catalog.tableExists(f"{CATALOG}.{SCHEMA}.{table}")

required = [
    "silver_311_service_requests",
    "gold_neighborhood_pulse",
    "gold_dim_community_area",
]

missing = [t for t in required if not exists(t)]
if missing:
    raise RuntimeError("Missing required tables: " + ", ".join(missing))

print(f"Using namespace: {CATALOG}.{SCHEMA}")

# COMMAND ----------

spark.sql(f'''
CREATE OR REPLACE TABLE `{CATALOG}`.`{SCHEMA}`.`gold_311_service_semantic_base` AS
SELECT
    DATE_TRUNC('MONTH', created_date) AS metric_month,
    community_area,
    sr_type AS service_request_type,
    COUNT(*) AS service_request_count,
    SUM(CASE WHEN UPPER(status) LIKE '%OPEN%' THEN 1 ELSE 0 END) AS open_request_count,
    SUM(CASE WHEN closed_at IS NOT NULL THEN 1 ELSE 0 END) AS closed_request_count,
    SUM(CASE WHEN resolution_days >= 0 THEN 1 ELSE 0 END) AS resolved_request_count,
    SUM(CASE WHEN resolution_days >= 0 THEN resolution_days ELSE 0 END) AS total_resolution_days
FROM `{CATALOG}`.`{SCHEMA}`.`silver_311_service_requests`
WHERE community_area BETWEEN 1 AND 77
  AND created_date IS NOT NULL
  AND sr_type IS NOT NULL
GROUP BY DATE_TRUNC('MONTH', created_date), community_area, sr_type
''')

spark.sql(f'''
COMMENT ON TABLE `{CATALOG}`.`{SCHEMA}`.`gold_311_service_semantic_base`
IS 'Monthly 311 semantic base by Community Area and service request type. Contains additive components for safe re-aggregation in Metric Views.'
''')

display(spark.sql(f'''
SELECT
    MIN(metric_month) AS min_month,
    MAX(metric_month) AS max_month,
    COUNT(*) AS semantic_rows,
    COUNT(DISTINCT community_area) AS community_areas,
    COUNT(DISTINCT service_request_type) AS request_types
FROM `{CATALOG}`.`{SCHEMA}`.`gold_311_service_semantic_base`
'''))

# COMMAND ----------

neighborhood_sql = f'''
CREATE OR REPLACE VIEW `{CATALOG}`.`{SCHEMA}`.`mv_neighborhood_pulse`
WITH METRICS LANGUAGE YAML AS
$$
version: 1.1
comment: >
  Governed Chicago neighborhood metrics combining 311 service requests,
  business license activity, building permits, and building violations.
  Use this Metric View for cross-dataset and Community Area analysis.
  Only completed calendar months are included.

source: {CATALOG}.{SCHEMA}.gold_neighborhood_pulse
filter: source.is_complete_month = true

fields:
  - name: metric_month
    expr: source.metric_month
    comment: Completed calendar month represented by the metrics.
    display_name: Month
    synonyms: ['reporting month', 'calendar month', 'period']

  - name: community_area
    expr: source.community_area
    comment: Official Chicago Community Area number from 1 through 77.
    display_name: Community Area Number
    synonyms: ['area number', 'neighborhood number']

  - name: community_area_name
    expr: source.community_area_name
    comment: Official Chicago Community Area name.
    display_name: Community Area
    synonyms: ['neighborhood', 'area', 'Chicago neighborhood', 'community', 'district']

measures:
  - name: total_311_requests
    expr: SUM(source.service_request_count)
    comment: Total number of 311 service requests created.
    display_name: 311 Service Requests
    synonyms: ['311 requests', 'complaints', 'service requests', 'resident complaints', '311 complaints']

  - name: open_311_requests
    expr: SUM(source.open_request_count)
    comment: Number of 311 requests classified as open.
    display_name: Open 311 Requests
    synonyms: ['open complaints', 'unresolved 311 requests']

  - name: closed_311_requests
    expr: SUM(source.closed_request_count)
    comment: Number of 311 requests with a close timestamp.
    display_name: Closed 311 Requests
    synonyms: ['closed complaints', 'completed 311 requests']

  - name: total_business_license_issues
    expr: SUM(source.new_license_issues)
    comment: Business license records whose application type is ISSUE.
    display_name: Business License Issues
    synonyms: ['new business licenses', 'license issues', 'business license activity', 'licenses issued']

  - name: total_building_permits
    expr: SUM(source.permit_count)
    comment: Total number of building permits issued.
    display_name: Building Permits
    synonyms: ['permits', 'permit activity', 'development permits', 'construction permits']

  - name: new_construction_permits
    expr: SUM(source.new_construction_permit_count)
    comment: Building permits categorized as new construction.
    display_name: New Construction Permits
    synonyms: ['new construction', 'new development permits']

  - name: total_permit_fees
    expr: SUM(source.total_permit_fees)
    comment: Total building permit fees represented by the selected records.
    display_name: Permit Fees
    synonyms: ['building permit fees', 'permit fee amount']

  - name: total_building_violations
    expr: SUM(source.violation_count)
    comment: Total building violations spatially mapped to Community Areas.
    display_name: Building Violations
    synonyms: ['violations', 'building issues', 'code violations', 'property violations']

  - name: open_building_violations
    expr: SUM(source.open_violation_count)
    comment: Building violations whose source status is open.
    display_name: Open Building Violations
    synonyms: ['open violations', 'unresolved building violations']

  - name: current_month_311_requests
    expr: SUM(source.service_request_count)
    display_name: Current Month 311 Requests
    window:
      - order: metric_month
        range: current
        semiadditive: last

  - name: previous_month_311_requests
    expr: SUM(source.service_request_count)
    display_name: Previous Month 311 Requests
    window:
      - order: metric_month
        range: trailing 1 month
        semiadditive: last

  - name: request_mom_change_pct
    expr: >
      (MEASURE(current_month_311_requests) - MEASURE(previous_month_311_requests))
      / NULLIF(MEASURE(previous_month_311_requests), 0) * 100
    comment: Percent change in 311 request volume versus the prior completed month.
    display_name: 311 Request Month-over-Month Change
    synonyms: ['complaint growth', '311 growth', 'month over month complaint change', 'MoM 311 change']

  - name: current_month_violations
    expr: SUM(source.violation_count)
    display_name: Current Month Building Violations
    window:
      - order: metric_month
        range: current
        semiadditive: last

  - name: previous_month_violations
    expr: SUM(source.violation_count)
    display_name: Previous Month Building Violations
    window:
      - order: metric_month
        range: trailing 1 month
        semiadditive: last

  - name: violation_mom_change_pct
    expr: >
      (MEASURE(current_month_violations) - MEASURE(previous_month_violations))
      / NULLIF(MEASURE(previous_month_violations), 0) * 100
    comment: Percent change in building violation volume versus the prior month.
    display_name: Building Violation Month-over-Month Change
    synonyms: ['violation growth', 'building violation change', 'MoM violation change']
$$
'''

spark.sql(neighborhood_sql)
print(f"Created {CATALOG}.{SCHEMA}.mv_neighborhood_pulse")

# COMMAND ----------

service_sql = f'''
CREATE OR REPLACE VIEW `{CATALOG}`.`{SCHEMA}`.`mv_311_service_trends`
WITH METRICS LANGUAGE YAML AS
$$
version: 1.1
comment: >
  Governed 311 service request metrics by completed month,
  Community Area, and service request type. Use this Metric View
  for complaint categories, request types, resolution time, and detailed 311 trends.

source: {CATALOG}.{SCHEMA}.gold_311_service_semantic_base
filter: source.metric_month < DATE_TRUNC('MONTH', CURRENT_DATE())

joins:
  - name: community
    source: {CATALOG}.{SCHEMA}.gold_dim_community_area
    'on': source.community_area = community.community_area
    rely:
      at_most_one_match: true

fields:
  - name: metric_month
    expr: source.metric_month
    display_name: Month
    synonyms: ['reporting month', 'calendar month', 'period']

  - name: community_area
    expr: source.community_area
    display_name: Community Area Number
    synonyms: ['area number', 'neighborhood number']

  - name: community_area_name
    expr: community.community_area_name
    display_name: Community Area
    synonyms: ['neighborhood', 'area', 'Chicago neighborhood', 'community']

  - name: service_request_type
    expr: source.service_request_type
    display_name: 311 Service Request Type
    synonyms: ['complaint type', 'request type', '311 category', 'complaint category', 'service type']

measures:
  - name: total_311_requests
    expr: SUM(source.service_request_count)
    display_name: 311 Service Requests
    synonyms: ['311 requests', 'complaints', 'service requests', 'resident complaints']

  - name: open_311_requests
    expr: SUM(source.open_request_count)
    display_name: Open 311 Requests
    synonyms: ['open complaints', 'unresolved requests']

  - name: closed_311_requests
    expr: SUM(source.closed_request_count)
    display_name: Closed 311 Requests
    synonyms: ['closed complaints', 'completed requests']

  - name: resolved_311_requests
    expr: SUM(source.resolved_request_count)
    display_name: Resolved 311 Requests
    synonyms: ['resolved complaints', 'resolved requests']

  - name: average_resolution_days
    expr: >
      SUM(source.total_resolution_days)
      / NULLIF(SUM(source.resolved_request_count), 0)
    comment: Weighted average number of days to resolution.
    display_name: Average Resolution Days
    synonyms: ['average resolution time', 'time to resolve', 'complaint resolution time', 'days to close']

  - name: current_month_311_requests
    expr: SUM(source.service_request_count)
    display_name: Current Month 311 Requests
    window:
      - order: metric_month
        range: current
        semiadditive: last

  - name: previous_month_311_requests
    expr: SUM(source.service_request_count)
    display_name: Previous Month 311 Requests
    window:
      - order: metric_month
        range: trailing 1 month
        semiadditive: last

  - name: request_mom_change_pct
    expr: >
      (MEASURE(current_month_311_requests) - MEASURE(previous_month_311_requests))
      / NULLIF(MEASURE(previous_month_311_requests), 0) * 100
    display_name: 311 Request Month-over-Month Change
    synonyms: ['complaint growth', 'request growth', 'MoM change', 'month over month change']
$$
'''

spark.sql(service_sql)
print(f"Created {CATALOG}.{SCHEMA}.mv_311_service_trends")

# COMMAND ----------

display(spark.sql(f"SHOW TABLES IN `{CATALOG}`.`{SCHEMA}`"))

display(spark.sql(
    f"DESCRIBE TABLE EXTENDED `{CATALOG}`.`{SCHEMA}`.`mv_neighborhood_pulse` AS JSON"
))

display(spark.sql(
    f"DESCRIBE TABLE EXTENDED `{CATALOG}`.`{SCHEMA}`.`mv_311_service_trends` AS JSON"
))

# COMMAND ----------

# MAGIC %md
# MAGIC After this notebook succeeds, run Notebook 11.
# MAGIC
# MAGIC Recommended Genie semantic sources after validation:
# MAGIC
# MAGIC `mv_neighborhood_pulse`
# MAGIC
# MAGIC `mv_311_service_trends`
# MAGIC
# MAGIC Supporting freshness source:
# MAGIC
# MAGIC `gold_data_freshness`