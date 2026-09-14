# Databricks notebook source
# MAGIC %md
# MAGIC # ChicagoPulse 01: Bronze Ingestion
# MAGIC
# MAGIC This notebook ingests Chicago public data into Delta tables.
# MAGIC
# MAGIC Default first run:
# MAGIC
# MAGIC `311 Service Requests only`
# MAGIC
# MAGIC After that works, add the other datasets one at a time.
# MAGIC
# MAGIC Official datasets used:
# MAGIC
# MAGIC * 311 Service Requests: `v6vf-nfxy`
# MAGIC * Business Licenses: `r5kz-chrr`
# MAGIC * Building Violations: `22u3-xenr`
# MAGIC * Building Permits: `ydr8-5enu`
# MAGIC
# MAGIC The code intentionally limits rows for the first prototype. The full 311 dataset is very large, so do not start by downloading everything into Free Edition.

# COMMAND ----------

import json
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

from pyspark.sql import functions as F
from pyspark.sql.types import StructType, StructField, StringType

CATALOG = spark.sql("SELECT current_catalog()").first()[0]

SCHEMA = "chicagopulse"

# FIRST RUN: keep this as ["311"].
# Later examples:
# DATASETS_TO_RUN = ["311", "business_licenses"]
# DATASETS_TO_RUN = ["311", "business_licenses", "building_violations", "building_permits"]
DATASETS_TO_RUN = ["building_violations"]

# Free Edition friendly limits.
# Increase these only after the first run succeeds.
PAGE_SIZE = 10_000
MAX_ROWS_PER_DATASET = 250_000

# Optional Socrata application token.
# Public reads work without one, but a token can improve API limits.
SOCRATA_APP_TOKEN = None

SOURCE_MODE = "api"   # "api" or "csv"

# COMMAND ----------

DATASETS = {
    "311": {
        "dataset_id": "v6vf-nfxy",
        "table": "bronze_311_service_requests",
        "primary_key": "sr_number",
        "date_field": "created_date",
        "lookback_days": 90,
        "fields": [
            "sr_number",
            "sr_type",
            "sr_short_code",
            "created_department",
            "owner_department",
            "status",
            "origin",
            "created_date",
            "last_modified_date",
            "closed_date",
            "street_address",
            "city",
            "state",
            "zip_code",
            "ward",
            "community_area",
            "latitude",
            "longitude"
        ],
        "csv_path": None,
    },

    "business_licenses": {
        "dataset_id": "r5kz-chrr",
        "table": "bronze_business_licenses",
        "primary_key": "id",
        "date_field": "license_start_date",
        "lookback_days": 730,
        "fields": [
            "id",
            "license_id",
            "account_number",
            "legal_name",
            "doing_business_as_name",
            "address",
            "ward",
            "community_area",
            "community_area_name",
            "neighborhood",
            "license_description",
            "application_type",
            "license_start_date",
            "expiration_date",
            "license_status",
            "license_status_change_date",
            "latitude",
            "longitude"
        ],
        "csv_path": None,
    },

    "building_violations": {
        "dataset_id": "22u3-xenr",
        "table": "bronze_building_violations",
        "primary_key": "id",
        "date_field": "violation_date",
        "lookback_days": 730,
        "fields": [
            "id",
            "violation_date",
            "violation_code",
            "violation_status",
            "violation_status_date",
            "violation_description",
            "violation_inspector_comments",
            "inspection_category",
            "department_bureau",
            "address",
            "latitude",
            "longitude"
        ],
        "csv_path": None,
    },

    "building_permits": {
        "dataset_id": "ydr8-5enu",
        "table": "bronze_building_permits",
        "primary_key": "id",
        "date_field": "issue_date",
        "lookback_days": 730,
        "fields": [
            "id",
            "permit_",
            "permit_status",
            "permit_milestone",
            "permit_type",
            "application_start_date",
            "issue_date",
            "processing_time",
            "street_number",
            "street_direction",
            "street_name",
            "work_type",
            "work_description",
            "total_fee",
            "community_area",
            "ward",
            "latitude",
            "longitude"
        ],
        "csv_path": None,
    },
}

# COMMAND ----------

def http_json(url, timeout=60):
    headers = {
        "User-Agent": "ChicagoPulse-Databricks-Free-Edition/1.0"
    }
    if SOCRATA_APP_TOKEN:
        headers["X-App-Token"] = SOCRATA_APP_TOKEN

    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def get_available_fields(dataset_id):
    metadata_url = f"https://data.cityofchicago.org/api/views/{dataset_id}"
    metadata = http_json(metadata_url)
    return {
        c.get("fieldName")
        for c in metadata.get("columns", [])
        if c.get("fieldName")
    }


def build_api_url(dataset_id, fields, where=None, order_by=None, limit=10000, offset=0):
    params = {
        "$select": ",".join(fields),
        "$limit": str(limit),
        "$offset": str(offset),
    }
    if where:
        params["$where"] = where
    if order_by:
        params["$order"] = order_by

    return (
        f"https://data.cityofchicago.org/resource/{dataset_id}.json?"
        + urllib.parse.urlencode(params)
    )


def rows_to_string_df(rows, fields):
    schema = StructType([StructField(f, StringType(), True) for f in fields])

    normalized = []
    for row in rows:
        values = []
        for field in fields:
            value = row.get(field)
            if isinstance(value, (dict, list)):
                value = json.dumps(value)
            elif value is not None:
                value = str(value)
            values.append(value)
        normalized.append(tuple(values))

    return spark.createDataFrame(normalized, schema=schema)


def full_table_name(table):
    return f"`{CATALOG}`.`{SCHEMA}`.`{table}`"

# COMMAND ----------

def ingest_from_api(name, cfg):
    dataset_id = cfg["dataset_id"]
    target = full_table_name(cfg["table"])
    stage = full_table_name("_stage_" + cfg["table"])
    pk = cfg["primary_key"]
    date_field = cfg["date_field"]

    available = get_available_fields(dataset_id)

    fields = [f for f in cfg["fields"] if f in available]
    missing = [f for f in cfg["fields"] if f not in available]

    if pk not in fields:
        raise ValueError(f"Primary key {pk!r} not present in dataset metadata.")
    if date_field not in fields:
        raise ValueError(f"Date field {date_field!r} not present in dataset metadata.")

    if missing:
        print(f"{name}: skipping fields not found in current source metadata: {missing}")

    cutoff = (
        datetime.now(timezone.utc) - timedelta(days=cfg["lookback_days"])
    ).strftime("%Y-%m-%dT00:00:00")

    where = f"{date_field} >= '{cutoff}'"
    order_by = f"{date_field} DESC, {pk} DESC"

    spark.sql(f"DROP TABLE IF EXISTS {stage}")

    offset = 0
    total = 0
    wrote_stage = False

    while total < MAX_ROWS_PER_DATASET:
        limit = min(PAGE_SIZE, MAX_ROWS_PER_DATASET - total)

        url = build_api_url(
            dataset_id=dataset_id,
            fields=fields,
            where=where,
            order_by=order_by,
            limit=limit,
            offset=offset,
        )

        rows = http_json(url)

        if not rows:
            break

        page_df = (
            rows_to_string_df(rows, fields)
            .withColumn("_source_dataset_id", F.lit(dataset_id))
            .withColumn("_ingested_at", F.current_timestamp())
        )

        (
            page_df.write
            .format("delta")
            .mode("append")
            .option("mergeSchema", "true")
            .saveAsTable(stage)
        )

        wrote_stage = True
        batch_count = len(rows)
        total += batch_count
        offset += batch_count

        print(f"{name}: staged {total:,} rows")

        if batch_count < limit:
            break

        time.sleep(0.15)

    if not wrote_stage:
        print(f"{name}: no source rows matched the configured window.")
        return

    spark.sql(f"CREATE TABLE IF NOT EXISTS {target} AS SELECT * FROM {stage} WHERE 1 = 0")

    spark.sql(f'''
        MERGE INTO {target} AS t
        USING {stage} AS s
        ON t.`{pk}` = s.`{pk}`
        WHEN MATCHED THEN UPDATE SET *
        WHEN NOT MATCHED THEN INSERT *
    ''')

    spark.sql(f"DROP TABLE IF EXISTS {stage}")

    final_count = spark.table(f"{CATALOG}.{SCHEMA}.{cfg['table']}").count()
    print(f"{name}: target now contains {final_count:,} rows")

# COMMAND ----------

def ingest_from_csv(name, cfg):
    csv_path = cfg.get("csv_path")
    if not csv_path:
        raise ValueError(
            f"{name}: csv_path is empty. Upload the City of Chicago CSV to a "
            "Unity Catalog Volume, then set DATASETS[name]['csv_path']."
        )

    target_name = f"{CATALOG}.{SCHEMA}.{cfg['table']}"

    df = (
        spark.read
        .option("header", True)
        .option("inferSchema", False)
        .csv(csv_path)
    )

    # Normalize City portal column names to lower snake_case.
    for old_name in df.columns:
        new_name = re.sub(r"[^a-zA-Z0-9]+", "_", old_name.strip()).strip("_").lower()
        df = df.withColumnRenamed(old_name, new_name)

    df = (
        df.withColumn("_source_dataset_id", F.lit(cfg["dataset_id"]))
          .withColumn("_ingested_at", F.current_timestamp())
    )

    (
        df.write
        .format("delta")
        .mode("overwrite")
        .option("overwriteSchema", "true")
        .saveAsTable(target_name)
    )

    print(f"{name}: loaded CSV into {target_name}")

# COMMAND ----------

# The CSV fallback helper uses Python regex.
import re

for name in DATASETS_TO_RUN:
    if name not in DATASETS:
        raise ValueError(f"Unknown dataset: {name}")

    print(f"\n===== {name} =====")

    try:
        if SOURCE_MODE == "api":
            ingest_from_api(name, DATASETS[name])
        elif SOURCE_MODE == "csv":
            ingest_from_csv(name, DATASETS[name])
        else:
            raise ValueError("SOURCE_MODE must be 'api' or 'csv'.")

    except Exception as exc:
        print(f"FAILED: {name}")
        print(str(exc)[:1500])

        if SOURCE_MODE == "api":
            print(
                "\nIf the error is network related, Free Edition may be blocking "
                "outbound access. Download the CSV from the Chicago Data Portal, "
                "upload it to your UC landing Volume, set SOURCE_MODE='csv', "
                "and populate csv_path for this dataset."
            )
        raise

# COMMAND ----------

# Inspect the loaded Bronze tables.

display(
    spark.sql(f"SHOW TABLES IN `{CATALOG}`.`{SCHEMA}`")
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Recommended progression
# MAGIC
# MAGIC 1. Run only `311`.
# MAGIC 2. Confirm the Bronze table exists.
# MAGIC 3. Run the Silver notebook.
# MAGIC 4. Return here and add `business_licenses`.
# MAGIC 5. Add `building_permits`.
# MAGIC 6. Add `building_violations`.
# MAGIC
# MAGIC The starter deliberately uses a 90 day window and a row cap for 311. That is enough to prove the architecture before deciding how aggressively to expand ingestion.