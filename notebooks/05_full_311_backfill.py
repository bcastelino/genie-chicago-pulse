# Databricks notebook source
# MAGIC %md
# MAGIC # ChicagoPulse 05: Full 311 Historical Backfill
# MAGIC
# MAGIC This replaces the 250K prototype sample with the full 311 history.
# MAGIC
# MAGIC It loads month by month, checkpoints completed months, and can be rerun safely. Bronze preserves all fields currently exposed by the 311 API. The existing `bronze_311_service_requests` table is replaced only after every source month has completed.

# COMMAND ----------

import json, time, urllib.parse, urllib.request
from datetime import datetime, timezone
from dateutil.relativedelta import relativedelta
from pyspark.sql import functions as F
from pyspark.sql.types import StructField, StructType, StringType
from pyspark.sql.window import Window

CATALOG = spark.sql("SELECT current_catalog()").first()[0]
SCHEMA = "chicagopulse"
DATASET_ID = "v6vf-nfxy"

TARGET_TABLE = "bronze_311_service_requests"
STAGE_TABLE = "bronze_311_service_requests_full_stage"
LOG_TABLE = "bronze_311_backfill_log"

PAGE_SIZE = 40_000
MAX_MONTHS_PER_RUN = 12  # Set None to attempt every remaining month.
RESET_BACKFILL = False
SOCRATA_APP_TOKEN = None

def fq(table):
    return f"`{CATALOG}`.`{SCHEMA}`.`{table}`"

print(f"Using {CATALOG}.{SCHEMA}")

# COMMAND ----------

def http_json(url, timeout=120, max_retries=6):

    headers = {
        "User-Agent":
            "ChicagoPulse-Databricks-Free-Edition/2.0"
    }

    if SOCRATA_APP_TOKEN:
        headers["X-App-Token"] = SOCRATA_APP_TOKEN

    for attempt in range(1, max_retries + 1):

        try:

            request = urllib.request.Request(
                url,
                headers=headers
            )

            with urllib.request.urlopen(
                request,
                timeout=timeout
            ) as response:

                raw = response.read()

                return json.loads(
                    raw.decode("utf-8")
                )

        except (
            http.client.IncompleteRead,
            urllib.error.URLError,
            urllib.error.HTTPError,
            TimeoutError,
            socket.timeout,
            ConnectionResetError,
            json.JSONDecodeError
        ) as exc:

            if attempt == max_retries:
                print(
                    f"API request failed after "
                    f"{max_retries} attempts."
                )
                raise

            wait_seconds = min(
                2 ** attempt + random.random(),
                30
            )

            print(
                f"API request failed on attempt "
                f"{attempt}/{max_retries}: "
                f"{type(exc).__name__}"
            )

            print(
                f"Retrying in "
                f"{wait_seconds:.1f} seconds..."
            )

            time.sleep(wait_seconds)

def resource_url(params):
    return f"https://data.cityofchicago.org/resource/{DATASET_ID}.json?" + urllib.parse.urlencode(params)

def get_source_fields():
    meta=http_json(f"https://data.cityofchicago.org/api/views/{DATASET_ID}")
    return [c["fieldName"] for c in meta.get("columns",[]) if c.get("fieldName")]

def get_source_profile():
    rows=http_json(resource_url({
        "$select":"min(created_date) as min_date,max(created_date) as max_date,count(*) as row_count"
    }))
    if not rows:
        raise RuntimeError("Could not read source profile.")
    return rows[0]

def parse_ts(v):
    return datetime.fromisoformat(v.replace("Z","+00:00"))

def month_floor(v):
    return datetime(v.year,v.month,1,tzinfo=timezone.utc)

def month_range(start,end):
    cur=start
    while cur<=end:
        yield cur
        cur=cur+relativedelta(months=1)

# COMMAND ----------

source_fields=get_source_fields()
profile=get_source_profile()
source_min=parse_ts(profile["min_date"])
source_max=parse_ts(profile["max_date"])
source_count=int(profile["row_count"])

first_month=month_floor(source_min)
last_month=month_floor(source_max)
all_months=list(month_range(first_month,last_month))

print(f"Source rows now: {source_count:,}")
print(f"Source coverage: {source_min} through {source_max}")
print(f"Source fields: {len(source_fields)}")
print(f"Months to cover: {len(all_months)}")

# COMMAND ----------

if RESET_BACKFILL:
    spark.sql(f"DROP TABLE IF EXISTS {fq(STAGE_TABLE)}")
    spark.sql(f"DROP TABLE IF EXISTS {fq(LOG_TABLE)}")
    print("Backfill reset.")

spark.sql(f'''
CREATE TABLE IF NOT EXISTS {fq(LOG_TABLE)} (
    month_key STRING,
    status STRING,
    rows_loaded BIGINT,
    event_at TIMESTAMP,
    message STRING
) USING DELTA
''')

def completed_months():
    return {
        r["month_key"]
        for r in spark.sql(
            f"SELECT DISTINCT month_key FROM {fq(LOG_TABLE)} WHERE status='COMPLETED'"
        ).collect()
    }

def log_event(month_key,status,rows_loaded=0,message=None):
    df=spark.createDataFrame(
        [(month_key,status,int(rows_loaded),datetime.utcnow(),message)],
        "month_key string,status string,rows_loaded long,event_at timestamp,message string"
    )
    df.write.format("delta").mode("append").saveAsTable(f"{CATALOG}.{SCHEMA}.{LOG_TABLE}")

# COMMAND ----------

def rows_to_df(rows, fields):
    schema=StructType([StructField(f,StringType(),True) for f in fields])
    normalized=[]
    for row in rows:
        vals=[]
        for f in fields:
            v=row.get(f)
            if isinstance(v,(dict,list)):
                v=json.dumps(v,separators=(",",":"))
            elif v is not None:
                v=str(v)
            vals.append(v)
        normalized.append(tuple(vals))
    return spark.createDataFrame(normalized,schema)

def load_month(month_start):
    month_end=month_start+relativedelta(months=1)
    key=month_start.strftime("%Y-%m-01")

    print(f"\nLoading {key}")

    if spark.catalog.tableExists(f"{CATALOG}.{SCHEMA}.{STAGE_TABLE}"):
        spark.sql(f"DELETE FROM {fq(STAGE_TABLE)} WHERE _backfill_month='{key}'")

    log_event(key,"STARTED",message="Backfill started")

    where=(
        f"created_date >= '{month_start.strftime('%Y-%m-%dT00:00:00')}' "
        f"AND created_date < '{month_end.strftime('%Y-%m-%dT00:00:00')}'"
    )

    offset=0
    total=0

    while True:
        rows=http_json(resource_url({
            "$select":",".join(source_fields),
            "$where":where,
            "$order":"created_date ASC, sr_number ASC",
            "$limit":str(PAGE_SIZE),
            "$offset":str(offset),
        }))

        if not rows:
            break

        df=(rows_to_df(rows,source_fields)
            .withColumn("_source_dataset_id",F.lit(DATASET_ID))
            .withColumn("_ingested_at",F.current_timestamp())
            .withColumn("_backfill_month",F.lit(key)))

        (df.write.format("delta").mode("append")
           .option("mergeSchema","true")
           .saveAsTable(f"{CATALOG}.{SCHEMA}.{STAGE_TABLE}"))

        n=len(rows)
        total+=n
        offset+=n
        print(f"{key}: {total:,}")

        if n<PAGE_SIZE:
            break
        time.sleep(0.1)

    log_event(key,"COMPLETED",rows_loaded=total,message="Backfill completed")
    print(f"{key}: complete with {total:,} rows")

# COMMAND ----------

done=completed_months()
remaining=[m for m in all_months if m.strftime("%Y-%m-01") not in done]
months_this_run=remaining if MAX_MONTHS_PER_RUN is None else remaining[:MAX_MONTHS_PER_RUN]

print(f"Completed: {len(done)} / {len(all_months)}")
print(f"Running this time: {len(months_this_run)} month(s)")

for month in months_this_run:
    try:
        load_month(month)
    except Exception as exc:
        log_event(month.strftime("%Y-%m-01"),"FAILED",message=str(exc)[:1000])
        raise

# COMMAND ----------

done=completed_months()
remaining=[m.strftime("%Y-%m-01") for m in all_months if m.strftime("%Y-%m-01") not in done]

if remaining:
    print(f"Backfill not finished. {len(remaining)} month(s) remain.")
    print("Rerun this notebook. Next:", remaining[:12])
else:
    print("All source months complete. Promoting full Bronze 311 table.")

    stage=spark.table(f"{CATALOG}.{SCHEMA}.{STAGE_TABLE}")
    w=Window.partitionBy("sr_number").orderBy(F.col("_ingested_at").desc())

    final=(stage
        .withColumn("_rn",F.row_number().over(w))
        .filter(F.col("_rn")==1)
        .drop("_rn","_backfill_month"))

    (final.write.format("delta").mode("overwrite")
        .option("overwriteSchema","true")
        .saveAsTable(f"{CATALOG}.{SCHEMA}.{TARGET_TABLE}"))

    count=spark.table(f"{CATALOG}.{SCHEMA}.{TARGET_TABLE}").count()
    print(f"Promoted {count:,} 311 rows.")

# COMMAND ----------

display(spark.sql(f'''
SELECT month_key,
       MAX(CASE WHEN status='COMPLETED' THEN rows_loaded END) AS rows_loaded,
       MAX(event_at) AS last_event
FROM {fq(LOG_TABLE)}
GROUP BY month_key
ORDER BY month_key
'''))

# COMMAND ----------

# MAGIC %md
# MAGIC If months remain, rerun this notebook. Do not run notebook 08 until the full Bronze table has been promoted.
# MAGIC
# MAGIC If Free Edition gives you enough compute headroom, set `MAX_MONTHS_PER_RUN = None`.