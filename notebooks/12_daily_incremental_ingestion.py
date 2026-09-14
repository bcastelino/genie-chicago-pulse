# Databricks notebook source
# MAGIC %md
# MAGIC # ChicagoPulse 12: Daily Incremental Ingestion
# MAGIC
# MAGIC Fetch only source rows changed since the previous successful refresh using Socrata `:updated_at`.
# MAGIC
# MAGIC The notebook uses:
# MAGIC - a 24-hour overlap
# MAGIC - persistent watermarks
# MAGIC - source-replacement safety limits
# MAGIC - staging Delta tables
# MAGIC - Delta MERGE into Bronze
# MAGIC - affected-month tracking for downstream refresh
# MAGIC
# MAGIC It deduplicates each source batch by its target business key before Delta MERGE and treats Socrata source row IDs as strings.
# MAGIC

# COMMAND ----------

import json, random, socket, time, uuid, http.client
import urllib.error, urllib.parse, urllib.request
from datetime import datetime, timedelta, timezone
from pyspark.sql import functions as F
from pyspark.sql.window import Window
from pyspark.sql.types import StructField, StructType, StringType

CATALOG = spark.sql("SELECT current_catalog()").first()[0]
SCHEMA = "chicagopulse"

PAGE_SIZE = 20_000
OVERLAP_HOURS = 24
BOOTSTRAP_LOOKBACK_DAYS = 7
SOCRATA_APP_TOKEN = None

RUN_ID = uuid.uuid4().hex
RUN_STARTED_AT = datetime.now(timezone.utc).replace(tzinfo=None)
QUERY_UNTIL_UTC = datetime.now(timezone.utc)

def fq(table):
    return f"`{CATALOG}`.`{SCHEMA}`.`{table}`"

print("Run ID:", RUN_ID)
print("Namespace:", f"{CATALOG}.{SCHEMA}")

# COMMAND ----------

DATASETS = {
    "311": {
        "dataset_id": "v6vf-nfxy",
        "table": "bronze_311_service_requests",
        "stage": "stage_daily_311_service_requests",
        "primary_key": "sr_number",
        "business_date": "created_date",
        "lookback_days": None,
        "max_changed_rows": 2_000_000,
        "fields": None,
    },
    "business_licenses": {
        "dataset_id": "r5kz-chrr",
        "table": "bronze_business_licenses",
        "stage": "stage_daily_business_licenses",
        "primary_key": "id",
        "business_date": "license_start_date",
        "lookback_days": 730,
        "max_changed_rows": 250_000,
        "fields": [
            "id","license_id","account_number","legal_name","doing_business_as_name",
            "address","ward","community_area","community_area_name","neighborhood",
            "license_description","application_type","license_start_date","expiration_date",
            "license_status","license_status_change_date","latitude","longitude"
        ],
    },
    "building_permits": {
        "dataset_id": "ydr8-5enu",
        "table": "bronze_building_permits",
        "stage": "stage_daily_building_permits",
        "primary_key": "id",
        "business_date": "issue_date",
        "lookback_days": 730,
        "max_changed_rows": 250_000,
        "fields": [
            "id","permit_","permit_status","permit_milestone","permit_type",
            "application_start_date","issue_date","processing_time","street_number",
            "street_direction","street_name","work_type","work_description","total_fee",
            "community_area","ward","latitude","longitude"
        ],
    },
    "building_violations": {
        "dataset_id": "22u3-xenr",
        "table": "bronze_building_violations",
        "stage": "stage_daily_building_violations",
        "primary_key": "id",
        "business_date": "violation_date",
        "lookback_days": 730,
        "max_changed_rows": 300_000,
        "fields": [
            "id","violation_date","violation_code","violation_status",
            "violation_status_date","violation_description","violation_inspector_comments",
            "inspection_category","department_bureau","address","latitude","longitude"
        ],
    },
}

# COMMAND ----------

def http_json(url, timeout=120, max_retries=6):
    headers = {"User-Agent":"ChicagoPulse-Daily-Refresh/1.0"}
    if SOCRATA_APP_TOKEN:
        headers["X-App-Token"] = SOCRATA_APP_TOKEN

    retryable = {408,429,500,502,503,504}

    for attempt in range(1, max_retries + 1):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code not in retryable or attempt == max_retries:
                raise
        except (
            http.client.IncompleteRead, urllib.error.URLError, TimeoutError,
            socket.timeout, ConnectionResetError, json.JSONDecodeError
        ):
            if attempt == max_retries:
                raise

        wait = min((2 ** attempt) + random.random(), 30)
        print(f"Retrying API request in {wait:.1f}s")
        time.sleep(wait)

def resource_url(dataset_id, params):
    return f"https://data.cityofchicago.org/resource/{dataset_id}.json?" + urllib.parse.urlencode(params)

def source_fields(dataset_id):
    meta = http_json(f"https://data.cityofchicago.org/api/views/{dataset_id}")
    return [c["fieldName"] for c in meta.get("columns",[]) if c.get("fieldName")]

def iso_utc(dt):
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")

def rows_to_df(rows, fields, dataset_id):
    cols = fields + [
        "source_row_id","source_updated_at","_source_dataset_id",
        "_ingested_at","_refresh_run_id"
    ]
    schema = StructType([StructField(c, StringType(), True) for c in cols])
    values = []

    for row in rows:
        rec = []
        for field in fields:
            v = row.get(field)
            if isinstance(v,(dict,list)):
                v = json.dumps(v,separators=(",",":"))
            elif v is not None:
                v = str(v)
            rec.append(v)

        rec += [
            str(row.get("source_row_id")) if row.get("source_row_id") is not None else None,
            str(row.get("source_updated_at")) if row.get("source_updated_at") is not None else None,
            dataset_id,
            datetime.now(timezone.utc).isoformat(),
            RUN_ID,
        ]
        values.append(tuple(rec))

    return spark.createDataFrame(values, schema)

# COMMAND ----------

spark.sql(f'''
CREATE TABLE IF NOT EXISTS {fq("etl_watermarks")} (
    dataset STRING,
    last_successful_updated_at TIMESTAMP,
    last_run_id STRING,
    updated_at TIMESTAMP
) USING DELTA
''')

spark.sql(f'''
CREATE TABLE IF NOT EXISTS {fq("etl_pipeline_runs")} (
    run_id STRING,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    status STRING,
    message STRING
) USING DELTA
''')

spark.sql(f'''
CREATE TABLE IF NOT EXISTS {fq("etl_dataset_runs")} (
    run_id STRING,
    dataset STRING,
    query_from TIMESTAMP,
    query_until TIMESTAMP,
    rows_detected BIGINT,
    rows_fetched BIGINT,
    status STRING,
    message STRING,
    completed_at TIMESTAMP
) USING DELTA
''')

spark.sql(f'''
CREATE TABLE IF NOT EXISTS {fq("etl_affected_periods")} (
    run_id STRING,
    dataset STRING,
    metric_month DATE
) USING DELTA
''')

spark.sql(f'''
CREATE OR REPLACE TABLE {fq("etl_current_run")} AS
SELECT
  '{RUN_ID}' AS run_id,
  TIMESTAMP('{RUN_STARTED_AT.isoformat(sep=" ")}') AS started_at,
  TIMESTAMP('{QUERY_UNTIL_UTC.replace(tzinfo=None).isoformat(sep=" ")}') AS query_until
''')

spark.createDataFrame(
    [(RUN_ID,RUN_STARTED_AT,None,"RUNNING","Incremental ingestion started")],
    "run_id string, started_at timestamp, completed_at timestamp, status string, message string"
).write.format("delta").mode("append").saveAsTable(
    f"{CATALOG}.{SCHEMA}.etl_pipeline_runs"
)

# COMMAND ----------

def get_watermark(dataset):
    rows = spark.sql(f'''
        SELECT last_successful_updated_at
        FROM {fq("etl_watermarks")}
        WHERE dataset = '{dataset}'
        ORDER BY updated_at DESC
        LIMIT 1
    ''').collect()

    if rows and rows[0]["last_successful_updated_at"]:
        return rows[0]["last_successful_updated_at"].replace(tzinfo=timezone.utc)

    return QUERY_UNTIL_UTC - timedelta(days=BOOTSTRAP_LOOKBACK_DAYS)

def build_where(cfg, query_from, query_until):
    clauses = [
        f":updated_at >= '{iso_utc(query_from)}'",
        f":updated_at <= '{iso_utc(query_until)}'",
    ]
    if cfg["lookback_days"] is not None:
        cutoff = (QUERY_UNTIL_UTC - timedelta(days=cfg["lookback_days"])).strftime("%Y-%m-%dT00:00:00")
        clauses.append(f"{cfg['business_date']} >= '{cutoff}'")
    return " AND ".join(clauses)

def count_changed(cfg, where):
    rows = http_json(resource_url(
        cfg["dataset_id"],
        {"$select":"count(*) as row_count","$where":where}
    ))
    return int(rows[0]["row_count"]) if rows else 0

# COMMAND ----------


def dedupe_stage(stage_df, primary_key):
    """
    Keep one current source row per target business key.

    Socrata datasets can contain multiple rows that map to the same ChicagoPulse
    business key. Delta MERGE requires at most one source row per target row.
    """
    window = (
        Window
        .partitionBy(primary_key)
        .orderBy(
            F.to_timestamp(F.col("source_updated_at")).desc_nulls_last(),
            F.col("source_row_id").desc_nulls_last(),
            F.col("_ingested_at").desc_nulls_last(),
        )
    )

    return (
        stage_df
        .filter(F.col(primary_key).isNotNull())
        .withColumn("_dedupe_rank", F.row_number().over(window))
        .filter(F.col("_dedupe_rank") == 1)
        .drop("_dedupe_rank")
    )


def ensure_target_columns(target_table, stage_df):
    existing = {f.name.lower() for f in spark.table(f"{CATALOG}.{SCHEMA}.{target_table}").schema.fields}
    for field in stage_df.schema.fields:
        if field.name.lower() not in existing:
            spark.sql(f'ALTER TABLE {fq(target_table)} ADD COLUMNS (`{field.name}` STRING)')
            print(f"Added {field.name} to {target_table}")

def merge_bronze(cfg, stage_df):
    ensure_target_columns(cfg["table"], stage_df)

    target_cols = [f.name for f in spark.table(f"{CATALOG}.{SCHEMA}.{cfg['table']}").schema.fields]
    shared = [c for c in stage_df.columns if c in target_cols]

    update_clause = ",\n".join([f"t.`{c}` = s.`{c}`" for c in shared])
    insert_cols = ", ".join([f"`{c}`" for c in shared])
    insert_vals = ", ".join([f"s.`{c}`" for c in shared])

    spark.sql(f'''
        MERGE INTO {fq(cfg["table"])} t
        USING {fq(cfg["stage"])} s
        ON t.`{cfg["primary_key"]}` = s.`{cfg["primary_key"]}`
        WHEN MATCHED THEN UPDATE SET {update_clause}
        WHEN NOT MATCHED THEN INSERT ({insert_cols}) VALUES ({insert_vals})
    ''')

def record_affected_periods(cfg):
    spark.sql(f'''
        INSERT INTO {fq("etl_affected_periods")}
        SELECT DISTINCT
          '{RUN_ID}',
          '{cfg["table"]}',
          CAST(DATE_TRUNC('MONTH', TRY_CAST(`{cfg["business_date"]}` AS DATE)) AS DATE)
        FROM {fq(cfg["stage"])}
        WHERE TRY_CAST(`{cfg["business_date"]}` AS DATE) IS NOT NULL
    ''')

def save_watermark(dataset, query_until):
    spark.sql(f"DELETE FROM {fq('etl_watermarks')} WHERE dataset = '{dataset}'")
    spark.sql(f'''
        INSERT INTO {fq("etl_watermarks")}
        VALUES (
          '{dataset}',
          TIMESTAMP('{query_until.replace(tzinfo=None).isoformat(sep=" ")}'),
          '{RUN_ID}',
          CURRENT_TIMESTAMP()
        )
    ''')

# COMMAND ----------

def ingest_dataset(name, cfg):
    stored = get_watermark(name)
    query_from = stored - timedelta(hours=OVERLAP_HOURS)
    query_until = QUERY_UNTIL_UTC
    where = build_where(cfg, query_from, query_until)

    detected = count_changed(cfg, where)

    print()
    print(name, "changed rows:", f"{detected:,}")

    if detected > cfg["max_changed_rows"]:
        raise RuntimeError(
            f"{name}: {detected:,} changed rows exceeds safety limit "
            f"{cfg['max_changed_rows']:,}. Possible source full replacement."
        )

    fields = source_fields(cfg["dataset_id"]) if cfg["fields"] is None else cfg["fields"]
    rows_all = []
    offset = 0

    while offset < detected:
        rows = http_json(resource_url(
            cfg["dataset_id"],
            {
                "$select":":id AS source_row_id,:updated_at AS source_updated_at," + ",".join(fields),
                "$where":where,
                "$order":f":updated_at ASC, {cfg['primary_key']} ASC",
                "$limit":str(PAGE_SIZE),
                "$offset":str(offset),
            }
        ))
        if not rows:
            break

        rows_all.extend(rows)
        offset += len(rows)
        print(f"Fetched {len(rows_all):,}/{detected:,}")

        if len(rows) < PAGE_SIZE:
            break

    if rows_all:
        stage_df = rows_to_df(rows_all, fields, cfg["dataset_id"])

        before_dedupe = stage_df.count()
        stage_df = dedupe_stage(stage_df, cfg["primary_key"])
        after_dedupe = stage_df.count()

        duplicate_source_rows = before_dedupe - after_dedupe

        print(
            f"Deduplicated {duplicate_source_rows:,} source row(s) "
            f"on {cfg['primary_key']}; {after_dedupe:,} unique row(s) remain."
        )
    else:
        empty_cols = fields + [
            "source_row_id","source_updated_at","_source_dataset_id",
            "_ingested_at","_refresh_run_id"
        ]
        stage_df = spark.createDataFrame(
            [],
            StructType([StructField(c,StringType(),True) for c in empty_cols])
        )

    (stage_df.write.format("delta").mode("overwrite")
        .option("overwriteSchema","true")
        .saveAsTable(f"{CATALOG}.{SCHEMA}.{cfg['stage']}"))

    if rows_all:
        record_affected_periods(cfg)
        merge_bronze(cfg, stage_df)

    save_watermark(name, query_until)

    spark.createDataFrame(
        [(RUN_ID,name,query_from.replace(tzinfo=None),query_until.replace(tzinfo=None),
          detected,len(rows_all),"SUCCESS",None,datetime.now(timezone.utc).replace(tzinfo=None))],
        "run_id string,dataset string,query_from timestamp,query_until timestamp,rows_detected long,rows_fetched long,status string,message string,completed_at timestamp"
    ).write.format("delta").mode("append").saveAsTable(
        f"{CATALOG}.{SCHEMA}.etl_dataset_runs"
    )

    return len(rows_all)

# COMMAND ----------

try:
    summary = []
    for name,cfg in DATASETS.items():
        summary.append((name,ingest_dataset(name,cfg)))

    spark.sql(f'''
        UPDATE {fq("etl_pipeline_runs")}
        SET status='INGESTION_COMPLETE',
            message='All source incremental ingestions completed'
        WHERE run_id='{RUN_ID}' AND status='RUNNING'
    ''')

    display(spark.createDataFrame(summary,["dataset","rows_fetched"]))
    display(spark.sql(f'''
        SELECT DISTINCT dataset,metric_month
        FROM {fq("etl_affected_periods")}
        WHERE run_id='{RUN_ID}'
        ORDER BY dataset,metric_month
    '''))
except Exception as exc:
    safe = str(exc)[:900].replace("'","''")
    spark.sql(f'''
        UPDATE {fq("etl_pipeline_runs")}
        SET completed_at=CURRENT_TIMESTAMP(),
            status='FAILED',
            message='{safe}'
        WHERE run_id='{RUN_ID}'
    ''')
    raise

# COMMAND ----------

# MAGIC %md
# MAGIC If this notebook stops on the source-replacement guard, do not raise the safety threshold immediately.
# MAGIC Investigate the source first. Socrata full replacements can make every row appear changed.