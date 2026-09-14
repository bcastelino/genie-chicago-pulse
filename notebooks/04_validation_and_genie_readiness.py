# Databricks notebook source
# MAGIC %md
# MAGIC # ChicagoPulse 04: Validation and Genie Readiness
# MAGIC
# MAGIC Validate the single-schema implementation and test the first ChicagoPulse analytical questions.
# MAGIC

# COMMAND ----------

CATALOG = spark.sql("SELECT current_catalog()").first()[0]
SCHEMA = "chicagopulse"


def exists(table):
    return spark.catalog.tableExists(
        f"{CATALOG}.{SCHEMA}.{table}"
    )


# COMMAND ----------

# Basic inventory across Bronze, Silver, and Gold.

tables = [
    "bronze_311_service_requests",
    "bronze_business_licenses",
    "bronze_building_violations",
    "bronze_building_permits",
    "silver_311_service_requests",
    "silver_business_licenses",
    "silver_building_violations",
    "silver_building_permits",
    "gold_dim_community_area",
    "gold_community_area_daily_metrics",
    "gold_community_area_monthly_metrics",
    "gold_service_type_trends",
    "gold_business_activity",
    "gold_building_activity",
    "gold_neighborhood_pulse",
]

inventory = []

for table in tables:
    if exists(table):
        df = spark.table(f"{CATALOG}.{SCHEMA}.{table}")
        inventory.append((table, df.count(), len(df.columns)))

display(
    spark.createDataFrame(
        inventory,
        ["table_name", "row_count", "column_count"]
    )
)


# COMMAND ----------

# Validate 311 primary key uniqueness if the Silver table exists.

if exists("silver_311_service_requests"):
    result = spark.sql(f'''
        SELECT
            COUNT(*) AS total_rows,
            COUNT(DISTINCT sr_number) AS distinct_sr_numbers,
            SUM(CASE WHEN sr_number IS NULL THEN 1 ELSE 0 END) AS null_sr_numbers
        FROM `{CATALOG}`.`{SCHEMA}`.`silver_311_service_requests`
    ''')
    display(result)


# COMMAND ----------

# First ChicagoPulse question:
# Which community areas are showing the strongest recent increase in 311 volume?

if exists("gold_community_area_monthly_metrics"):
    display(
        spark.sql(f'''
            SELECT
                m.metric_month,
                m.community_area,
                d.community_area_name,
                m.service_request_count,
                m.previous_month_request_count,
                m.request_count_mom_pct
            FROM `{CATALOG}`.`{SCHEMA}`.`gold_community_area_monthly_metrics` m
            LEFT JOIN `{CATALOG}`.`{SCHEMA}`.`gold_dim_community_area` d
              ON m.community_area = d.community_area
            WHERE m.metric_month = (
                SELECT MAX(metric_month)
                FROM `{CATALOG}`.`{SCHEMA}`.`gold_community_area_monthly_metrics`
            )
              AND m.previous_month_request_count IS NOT NULL
            ORDER BY m.request_count_mom_pct DESC
            LIMIT 15
        ''')
    )


# COMMAND ----------

# Second ChicagoPulse question:
# What request types are driving activity in those areas?

if exists("gold_service_type_trends"):
    display(
        spark.sql(f'''
            SELECT
                metric_month,
                community_area,
                sr_type,
                service_request_count
            FROM `{CATALOG}`.`{SCHEMA}`.`gold_service_type_trends`
            WHERE metric_month = (
                SELECT MAX(metric_month)
                FROM `{CATALOG}`.`{SCHEMA}`.`gold_service_type_trends`
            )
            ORDER BY service_request_count DESC
            LIMIT 25
        ''')
    )


# COMMAND ----------

# Cross dataset question, available after loading business licenses + permits:
# Where are complaints rising while new business activity is declining?

if exists("gold_neighborhood_pulse"):
    display(
        spark.sql(f'''
            SELECT
                metric_month,
                community_area,
                community_area_name,
                service_request_count,
                request_count_mom_pct,
                new_license_issues,
                previous_month_new_license_issues,
                permit_count,
                complaints_rising_flag,
                new_business_activity_declining_flag
            FROM `{CATALOG}`.`{SCHEMA}`.`gold_neighborhood_pulse`
            WHERE complaints_rising_flag = TRUE
              AND new_business_activity_declining_flag = TRUE
            ORDER BY metric_month DESC, request_count_mom_pct DESC
            LIMIT 25
        ''')
    )
else:
    print(
        "gold_neighborhood_pulse does not exist yet. "
        "Load 311 + business licenses + building permits first."
    )


# COMMAND ----------

# Add table descriptions that will help both humans and Genie.

comments = {
    "gold_community_area_daily_metrics":
        "Daily Chicago 311 service request metrics by community area.",
    "gold_community_area_monthly_metrics":
        "Monthly Chicago 311 service request metrics by community area, including month over month change.",
    "gold_service_type_trends":
        "Monthly 311 request counts by Chicago community area and service request type.",
    "gold_business_activity":
        "Monthly Chicago business license activity by community area.",
    "gold_building_activity":
        "Monthly Chicago building permit activity by community area.",
    "gold_neighborhood_pulse":
        "Cross dataset monthly neighborhood indicators combining 311, business license, and building permit activity."
}

for table, comment in comments.items():
    if exists(table):
        escaped = comment.replace("'", "''")
        spark.sql(
            f"COMMENT ON TABLE `{CATALOG}`.`{SCHEMA}`.`{table}` IS '{escaped}'"
        )
        print(f"Commented: {table}")


# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT
# MAGIC     '311' AS dataset,
# MAGIC     COUNT(*) AS rows,
# MAGIC     MIN(created_date) AS min_date,
# MAGIC     MAX(created_date) AS max_date
# MAGIC FROM workspace.chicagopulse.silver_311_service_requests
# MAGIC
# MAGIC UNION ALL
# MAGIC
# MAGIC SELECT
# MAGIC     'business_licenses',
# MAGIC     COUNT(*),
# MAGIC     MIN(license_start_date),
# MAGIC     MAX(license_start_date)
# MAGIC FROM workspace.chicagopulse.silver_business_licenses
# MAGIC
# MAGIC UNION ALL
# MAGIC
# MAGIC SELECT
# MAGIC     'building_permits',
# MAGIC     COUNT(*),
# MAGIC     MIN(issue_date),
# MAGIC     MAX(issue_date)
# MAGIC FROM workspace.chicagopulse.silver_building_permits
# MAGIC
# MAGIC UNION ALL
# MAGIC
# MAGIC SELECT
# MAGIC     'building_violations',
# MAGIC     COUNT(*),
# MAGIC     MIN(violation_date),
# MAGIC     MAX(violation_date)
# MAGIC FROM workspace.chicagopulse.silver_building_violations;

# COMMAND ----------

# MAGIC %md
# MAGIC ## Genie starting point
# MAGIC
# MAGIC Once these queries return sensible results:
# MAGIC
# MAGIC 1. Create a Genie space.
# MAGIC 2. Add the Gold tables, not the raw Bronze tables.
# MAGIC 3. Start with `gold_community_area_monthly_metrics`, `gold_service_type_trends`, `gold_business_activity`, `gold_building_activity`, and `gold_neighborhood_pulse`.
# MAGIC 4. Give Genie clear synonyms such as community area = neighborhood area, service request = 311 complaint/request.
# MAGIC 5. Test the benchmark questions in this notebook before wiring Genie into the app.
# MAGIC
# MAGIC Do not add all raw 311 columns to Genie simply because they are available. The Gold layer should carry the analytical meaning.
# MAGIC