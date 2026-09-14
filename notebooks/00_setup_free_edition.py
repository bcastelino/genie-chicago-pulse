# Databricks notebook source
# MAGIC %md
# MAGIC # ChicagoPulse 00: Free Edition Setup
# MAGIC
# MAGIC This notebook creates the Unity Catalog schemas used by the starter project.
# MAGIC
# MAGIC Run this notebook first.
# MAGIC
# MAGIC Architecture used in this starter:
# MAGIC
# MAGIC `Chicago Data Portal -> Bronze -> Silver -> Gold -> Genie / Databricks App`
# MAGIC
# MAGIC The notebook intentionally uses the catalog you are already attached to rather than creating a new catalog. This is friendlier to Databricks Free Edition permissions.

# COMMAND ----------

from datetime import datetime

CATALOG = spark.sql("SELECT current_catalog()").first()[0]

SCHEMA = "chicagopulse"
LANDING_VOLUME = "landing"

print(f"Using catalog: {CATALOG}")
print(f"Using schema:  {SCHEMA}")

# COMMAND ----------

spark.sql(f"CREATE SCHEMA IF NOT EXISTS `{CATALOG}`.`{SCHEMA}`")

print(f"Ready: {CATALOG}.{SCHEMA}")

# COMMAND ----------

volume_created = False

try:
    spark.sql(
        f"CREATE VOLUME IF NOT EXISTS "
        f"`{CATALOG}`.`{SCHEMA}`.`{LANDING_VOLUME}`"
    )

    volume_created = True

    print(
        "Landing volume ready:",
        f"/Volumes/{CATALOG}/{SCHEMA}/{LANDING_VOLUME}"
    )

except Exception as exc:
    print("Could not create the landing volume automatically.")
    print("You can still use direct API ingestion.")
    print(
        "If needed, create a Unity Catalog Volume manually "
        "through Catalog Explorer."
    )
    print("Reason:", str(exc)[:500])

# COMMAND ----------

config_rows = [
    ("catalog", CATALOG),
    ("schema", SCHEMA),
    ("landing_volume", LANDING_VOLUME),
]

config_df = spark.createDataFrame(
    config_rows,
    ["config_key", "config_value"]
)

(
    config_df.write
    .format("delta")
    .mode("overwrite")
    .saveAsTable(
        f"`{CATALOG}`.`{SCHEMA}`.`project_config`"
    )
)

display(config_df)

# COMMAND ----------

display(
    spark.sql(
        f"SHOW TABLES IN `{CATALOG}`.`{SCHEMA}`"
    )
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Next
# MAGIC
# MAGIC Run `01_bronze_ingestion.ipynb`.
# MAGIC
# MAGIC For your first run, leave `DATASETS_TO_RUN = ["311"]`.
# MAGIC
# MAGIC That gives us the first end to end slice without burning unnecessary Free Edition quota.