# Databricks notebook source
# MAGIC %md
# MAGIC # ChicagoPulse 02: Silver Transformations
# MAGIC
# MAGIC This notebook is self contained.

# COMMAND ----------

CATALOG = spark.sql("SELECT current_catalog()").first()[0]
SCHEMA = "chicagopulse"

def exists(table):
    return spark.catalog.tableExists(
        f"{CATALOG}.{SCHEMA}.{table}"
    )

def replace_table(table, query):
    spark.sql(
        f"CREATE OR REPLACE TABLE `{CATALOG}`.`{SCHEMA}`.`{table}` AS {query}"
    )
    print(f"Built {CATALOG}.{SCHEMA}.{table}")

print(f"Using {CATALOG}.{SCHEMA}")

# COMMAND ----------

if exists("bronze_311_service_requests"):
    replace_table(
        "silver_311_service_requests",
        f'''
        SELECT
            sr_number,
            sr_type,
            sr_short_code,
            created_department,
            owner_department,
            status,
            origin,
            CAST(created_date AS TIMESTAMP) AS created_at,
            CAST(created_date AS DATE) AS created_date,
            CAST(last_modified_date AS TIMESTAMP) AS last_modified_at,
            CAST(closed_date AS TIMESTAMP) AS closed_at,
            CAST(closed_date AS DATE) AS closed_date,
            CASE
                WHEN closed_date IS NOT NULL
                THEN DATEDIFF(
                    CAST(closed_date AS DATE),
                    CAST(created_date AS DATE)
                )
            END AS resolution_days,
            street_address,
            city,
            state,
            zip_code,
            CAST(ward AS INT) AS ward,
            CAST(community_area AS INT) AS community_area,
            CAST(latitude AS DOUBLE) AS latitude,
            CAST(longitude AS DOUBLE) AS longitude,
            _source_dataset_id,
            _ingested_at
        FROM `{CATALOG}`.`{SCHEMA}`.`bronze_311_service_requests`
        WHERE sr_number IS NOT NULL
        '''
    )
else:
    print("Skipping 311: bronze table not found.")

# COMMAND ----------

if exists("bronze_business_licenses"):
    replace_table(
        "silver_business_licenses",
        f'''
        SELECT
            id,
            CAST(license_id AS BIGINT) AS license_id,
            CAST(account_number AS BIGINT) AS account_number,
            legal_name,
            doing_business_as_name,
            address,
            CAST(ward AS INT) AS ward,
            CAST(community_area AS INT) AS community_area,
            community_area_name,
            neighborhood,
            license_description,
            application_type,
            CAST(license_start_date AS DATE) AS license_start_date,
            CASE
                WHEN expiration_date LIKE '9999-%' THEN NULL
                ELSE CAST(expiration_date AS DATE)
            END AS expiration_date,
            license_status,
            CAST(license_status_change_date AS DATE)
                AS license_status_change_date,
            CAST(latitude AS DOUBLE) AS latitude,
            CAST(longitude AS DOUBLE) AS longitude,
            _source_dataset_id,
            _ingested_at
        FROM `{CATALOG}`.`{SCHEMA}`.`bronze_business_licenses`
        WHERE id IS NOT NULL
        '''
    )
else:
    print("Skipping business licenses: bronze table not found.")

# COMMAND ----------

if exists("bronze_building_violations"):
    replace_table(
        "silver_building_violations",
        f'''
        SELECT
            id,
            CAST(violation_date AS DATE) AS violation_date,
            violation_code,
            UPPER(violation_status) AS violation_status,
            CAST(violation_status_date AS DATE) AS violation_status_date,
            violation_description,
            violation_inspector_comments,
            inspection_category,
            department_bureau,
            address,
            CAST(latitude AS DOUBLE) AS latitude,
            CAST(longitude AS DOUBLE) AS longitude,
            _source_dataset_id,
            _ingested_at
        FROM `{CATALOG}`.`{SCHEMA}`.`bronze_building_violations`
        WHERE id IS NOT NULL
        '''
    )
else:
    print("Skipping building violations: bronze table not found.")

# COMMAND ----------

if exists("bronze_building_permits"):
    replace_table(
        "silver_building_permits",
        f'''
        SELECT
            id,
            permit_ AS permit_number,
            permit_status,
            permit_milestone,
            permit_type,
            CAST(application_start_date AS DATE)
                AS application_start_date,
            CAST(issue_date AS DATE) AS issue_date,
            CAST(processing_time AS INT) AS processing_time_days,
            CONCAT_WS(
                ' ', street_number, street_direction, street_name
            ) AS address,
            work_type,
            work_description,
            CAST(total_fee AS DOUBLE) AS total_fee,
            CAST(community_area AS INT) AS community_area,
            CAST(ward AS INT) AS ward,
            CAST(latitude AS DOUBLE) AS latitude,
            CAST(longitude AS DOUBLE) AS longitude,
            _source_dataset_id,
            _ingested_at
        FROM `{CATALOG}`.`{SCHEMA}`.`bronze_building_permits`
        WHERE id IS NOT NULL
        '''
    )
else:
    print("Skipping building permits: bronze table not found.")

# COMMAND ----------

silver_tables = [
    "silver_311_service_requests",
    "silver_business_licenses",
    "silver_building_violations",
    "silver_building_permits",
]

rows = []
for table in silver_tables:
    if exists(table):
        df = spark.table(f"{CATALOG}.{SCHEMA}.{table}")
        rows.append((table, df.count(), len(df.columns)))

if rows:
    display(
        spark.createDataFrame(
            rows, ["table_name", "row_count", "column_count"]
        )
    )
else:
    print("No Silver tables were created.")