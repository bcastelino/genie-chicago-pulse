# Databricks notebook source
# MAGIC %md
# MAGIC # ChicagoPulse 09: Genie Readiness and Validation
# MAGIC
# MAGIC Final checks and semantic metadata before creating the Genie Space.
# MAGIC
# MAGIC Recommended Genie tables are listed at the end.

# COMMAND ----------

CATALOG=spark.sql("SELECT current_catalog()").first()[0]
SCHEMA="chicagopulse"

def exists(table):
    return spark.catalog.tableExists(f"{CATALOG}.{SCHEMA}.{table}")

required=[
    "silver_311_service_requests",
    "silver_business_licenses",
    "silver_building_permits",
    "silver_building_violations_enriched",
    "gold_dim_community_area",
    "gold_community_area_monthly_metrics",
    "gold_service_type_trends",
    "gold_business_activity",
    "gold_building_activity",
    "gold_building_violation_activity",
    "gold_neighborhood_pulse",
    "gold_latest_neighborhood_pulse",
]
missing=[t for t in required if not exists(t)]
if missing:
    raise RuntimeError("Missing Genie-ready tables: "+", ".join(missing))
print("All required tables exist.")

# COMMAND ----------

spark.sql(f'''
CREATE OR REPLACE TABLE `{CATALOG}`.`{SCHEMA}`.`gold_data_freshness` AS
SELECT '311 Service Requests' AS dataset,COUNT(*) AS row_count,
       MIN(created_date) AS min_date,MAX(created_date) AS max_date
FROM `{CATALOG}`.`{SCHEMA}`.`silver_311_service_requests`
UNION ALL
SELECT 'Business Licenses',COUNT(*),MIN(license_start_date),MAX(license_start_date)
FROM `{CATALOG}`.`{SCHEMA}`.`silver_business_licenses`
UNION ALL
SELECT 'Building Permits',COUNT(*),MIN(issue_date),MAX(issue_date)
FROM `{CATALOG}`.`{SCHEMA}`.`silver_building_permits`
UNION ALL
SELECT 'Building Violations',COUNT(*),MIN(violation_date),MAX(violation_date)
FROM `{CATALOG}`.`{SCHEMA}`.`silver_building_violations_enriched`
''')

display(spark.table(f"{CATALOG}.{SCHEMA}.gold_data_freshness"))

# COMMAND ----------

display(spark.sql(f'''
SELECT
    COUNT(*) AS total_311_rows,
    COUNT(DISTINCT sr_number) AS distinct_sr_numbers,
    COUNT(*)-COUNT(DISTINCT sr_number) AS duplicate_rows,
    MIN(created_date) AS min_created_date,
    MAX(created_date) AS max_created_date
FROM `{CATALOG}`.`{SCHEMA}`.`silver_311_service_requests`
'''))

display(spark.sql(f'''
SELECT geography_match_status,COUNT(*) AS rows,
       ROUND(100.0*COUNT(*)/SUM(COUNT(*)) OVER (),2) AS pct
FROM `{CATALOG}`.`{SCHEMA}`.`silver_building_violations_enriched`
GROUP BY geography_match_status
ORDER BY rows DESC
'''))

# COMMAND ----------

display(spark.sql(f'''
SELECT
    metric_month,
    COUNT(*) AS community_area_rows,
    SUM(CASE WHEN business_data_available THEN 1 ELSE 0 END) AS areas_with_business_data,
    SUM(CASE WHEN permit_data_available THEN 1 ELSE 0 END) AS areas_with_permit_data,
    SUM(CASE WHEN violation_data_available THEN 1 ELSE 0 END) AS areas_with_violation_data
FROM `{CATALOG}`.`{SCHEMA}`.`gold_neighborhood_pulse`
GROUP BY metric_month
ORDER BY metric_month DESC
LIMIT 24
'''))

# COMMAND ----------

comments={
"gold_dim_community_area":
"Authoritative dimension for Chicago's 77 official Community Areas, including boundary GeoJSON.",
"gold_community_area_monthly_metrics":
"Monthly 311 metrics by Chicago Community Area. Month over month percentage is populated only for completed months.",
"gold_service_type_trends":
"Monthly 311 request counts by Community Area and service request type.",
"gold_business_activity":
"Monthly Chicago business license activity by Community Area.",
"gold_building_activity":
"Monthly Chicago building permit activity by Community Area.",
"gold_building_violation_activity":
"Monthly building violation activity mapped to official Chicago Community Areas.",
"gold_neighborhood_pulse":
"Cross-dataset monthly neighborhood intelligence combining 311, business licenses, building permits, and building violations.",
"gold_latest_neighborhood_pulse":
"Neighborhood pulse for the latest fully completed month.",
"gold_data_freshness":
"Source row counts and date coverage for explaining dataset freshness."
}

for table,comment in comments.items():
    escaped=comment.replace("'","''")
    spark.sql(f"COMMENT ON TABLE `{CATALOG}`.`{SCHEMA}`.`{table}` IS '{escaped}'")
    print(f"Commented {table}")

# COMMAND ----------

dictionary_rows=[
("gold_neighborhood_pulse","community_area","Official Chicago Community Area number from 1 to 77."),
("gold_neighborhood_pulse","community_area_name","Official Chicago Community Area name. In ChicagoPulse, neighborhood and community area can be treated as user-facing synonyms."),
("gold_neighborhood_pulse","metric_month","Calendar month represented by the row."),
("gold_neighborhood_pulse","is_complete_month","True only after the represented calendar month has fully ended. Prefer complete months for month over month comparisons."),
("gold_neighborhood_pulse","service_request_count","Number of 311 service requests created in the Community Area during the month."),
("gold_neighborhood_pulse","request_count_mom_pct","Percent change in 311 request volume versus the previous month. Null for the current incomplete month."),
("gold_neighborhood_pulse","new_license_issues","Count of business license records with application type ISSUE."),
("gold_neighborhood_pulse","permit_count","Count of building permits issued."),
("gold_neighborhood_pulse","violation_count","Count of building violations spatially mapped to the Community Area."),
("gold_neighborhood_pulse","business_data_available","True when business license data exists for this Community Area and month. Do not interpret unavailable null values as zero."),
("gold_neighborhood_pulse","permit_data_available","True when building permit data exists for this Community Area and month. Do not interpret unavailable null values as zero."),
("gold_neighborhood_pulse","violation_data_available","True when mapped building violation data exists for this Community Area and month.")
]

df=spark.createDataFrame(dictionary_rows,["table_name","column_name","business_definition"])
df.write.format("delta").mode("overwrite").saveAsTable(
    f"{CATALOG}.{SCHEMA}.gold_genie_data_dictionary"
)
display(df)

# COMMAND ----------

# Benchmark 1: biggest 311 increases in the latest completed month
display(spark.sql(f'''
SELECT metric_month,community_area,community_area_name,
       service_request_count,previous_month_request_count,request_count_mom_pct
FROM `{CATALOG}`.`{SCHEMA}`.`gold_latest_neighborhood_pulse`
WHERE previous_month_request_count IS NOT NULL
ORDER BY request_count_mom_pct DESC
LIMIT 15
'''))

# Benchmark 2: rising complaints and building violations
display(spark.sql(f'''
SELECT metric_month,community_area,community_area_name,
       service_request_count,request_count_mom_pct,
       violation_count,previous_month_violation_count
FROM `{CATALOG}`.`{SCHEMA}`.`gold_neighborhood_pulse`
WHERE is_complete_month=TRUE
  AND complaints_rising_flag=TRUE
  AND building_violations_rising_flag=TRUE
ORDER BY metric_month DESC,request_count_mom_pct DESC
LIMIT 25
'''))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Add these tables to Genie
# MAGIC
# MAGIC `gold_neighborhood_pulse`
# MAGIC
# MAGIC `gold_latest_neighborhood_pulse`
# MAGIC
# MAGIC `gold_community_area_monthly_metrics`
# MAGIC
# MAGIC `gold_service_type_trends`
# MAGIC
# MAGIC `gold_business_activity`
# MAGIC
# MAGIC `gold_building_activity`
# MAGIC
# MAGIC `gold_building_violation_activity`
# MAGIC
# MAGIC `gold_dim_community_area`
# MAGIC
# MAGIC `gold_data_freshness`
# MAGIC
# MAGIC Do not add Bronze tables to Genie.
# MAGIC
# MAGIC Recommended synonyms:
# MAGIC
# MAGIC Community Area = neighborhood, area, Chicago neighborhood
# MAGIC
# MAGIC 311 Service Request = 311 request, complaint, service request
# MAGIC
# MAGIC Business License Issue = new license, business license activity
# MAGIC
# MAGIC Building Permit = permit, development activity
# MAGIC
# MAGIC Building Violation = violation, building issue
# MAGIC
# MAGIC Recommended Genie instruction:
# MAGIC
# MAGIC When comparing months, prefer `is_complete_month = true`. Never treat a null metric as zero when its corresponding `*_data_available` field is false.