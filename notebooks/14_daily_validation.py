# Databricks notebook source
# MAGIC %md
# MAGIC # ChicagoPulse 14: Daily Validation
# MAGIC
# MAGIC Final task in the daily Lakeflow Job.
# MAGIC
# MAGIC Severe validation failures raise an exception so the job is marked failed.

# COMMAND ----------

CATALOG=spark.sql("SELECT current_catalog()").first()[0]
SCHEMA="chicagopulse"

def fq(t):
    return f"`{CATALOG}`.`{SCHEMA}`.`{t}`"

run=spark.table(f"{CATALOG}.{SCHEMA}.etl_current_run").first()
RUN_ID=run["run_id"]

status=spark.sql(f'''
SELECT status FROM {fq("etl_pipeline_runs")}
WHERE run_id='{RUN_ID}'
ORDER BY started_at DESC LIMIT 1
''').first()["status"]

if status!="TRANSFORM_COMPLETE":
    raise RuntimeError(f"Run {RUN_ID} not ready. Status={status}")

checks=[]

def add_check(name,passed,value,severity="ERROR"):
    checks.append((name,bool(passed),str(value),severity))

# COMMAND ----------

n=spark.sql(f'''
SELECT COUNT(DISTINCT community_area) AS n
FROM {fq("gold_dim_community_area")}
''').first()["n"]

add_check("77 official Community Areas",n==77,n)

# COMMAND ----------

for table,pk in [
    ("silver_311_service_requests","sr_number"),
    ("silver_business_licenses","id"),
    ("silver_building_permits","id"),
    ("silver_building_violations","id"),
]:
    row=spark.sql(f'''
    SELECT COUNT(*) AS total_rows,
           COUNT(DISTINCT `{pk}`) AS distinct_rows
    FROM {fq(table)}
    ''').first()

    duplicates=row["total_rows"]-row["distinct_rows"]
    add_check(f"{table} primary-key duplicates",duplicates==0,duplicates)

# COMMAND ----------

row=spark.sql(f'''
SELECT
  SUM(CASE WHEN geography_match_status='MATCHED' THEN 1 ELSE 0 END) AS matched,
  COUNT(*) AS total
FROM {fq("silver_building_violations_enriched")}
''').first()

pct=100.0*row["matched"]/row["total"] if row["total"] else 0
add_check("Building violation geography match >= 99%",pct>=99.0,f"{pct:.2f}%")

# COMMAND ----------

latest=spark.sql(f'''
SELECT MAX(metric_month) AS m
FROM {fq("gold_neighborhood_pulse")}
WHERE is_complete_month=TRUE
''').first()["m"]

count=spark.sql(f'''
SELECT COUNT(*) AS n
FROM {fq("gold_neighborhood_pulse")}
WHERE is_complete_month=TRUE
  AND metric_month=TIMESTAMP('{latest}')
''').first()["n"]

add_check("Latest completed month has rows",count>0,f"{latest}: {count}")

# COMMAND ----------

requests=spark.sql(f'''
SELECT MEASURE(total_311_requests) AS requests
FROM {fq("mv_neighborhood_pulse")}
WHERE metric_month=(
  SELECT MAX(metric_month)
  FROM {fq("mv_neighborhood_pulse")}
)
''').first()["requests"]

add_check("mv_neighborhood_pulse queryable",requests is not None,requests)

service_requests=spark.sql(f'''
SELECT MEASURE(total_311_requests) AS requests
FROM {fq("mv_311_service_trends")}
WHERE metric_month=(
  SELECT MAX(metric_month)
  FROM {fq("mv_311_service_trends")}
)
''').first()["requests"]

add_check("mv_311_service_trends queryable",service_requests is not None,service_requests)

# COMMAND ----------

fresh=spark.table(f"{CATALOG}.{SCHEMA}.gold_data_freshness")
fresh_count=fresh.count()
add_check("gold_data_freshness has four sources",fresh_count==4,fresh_count)
display(fresh)

# COMMAND ----------

check_df=spark.createDataFrame(
    checks,
    ["check_name","passed","value","severity"]
)
display(check_df)

failures=[r for r in checks if not r[1] and r[3]=="ERROR"]

if failures:
    message="; ".join([f"{r[0]}={r[2]}" for r in failures])
    safe=message[:900].replace("'","''")

    spark.sql(f'''
    UPDATE {fq("etl_pipeline_runs")}
    SET completed_at=CURRENT_TIMESTAMP(),
        status='VALIDATION_FAILED',
        message='{safe}'
    WHERE run_id='{RUN_ID}'
    ''')

    raise RuntimeError("ChicagoPulse validation failed: "+message)

spark.sql(f'''
UPDATE {fq("etl_pipeline_runs")}
SET completed_at=CURRENT_TIMESTAMP(),
    status='SUCCESS',
    message='Daily refresh and validation completed successfully'
WHERE run_id='{RUN_ID}'
''')

print("ChicagoPulse daily refresh PASSED")
print("Run ID:",RUN_ID)

# COMMAND ----------

display(spark.sql(f'''
SELECT run_id,started_at,completed_at,status,message
FROM {fq("etl_pipeline_runs")}
ORDER BY started_at DESC
LIMIT 10
'''))