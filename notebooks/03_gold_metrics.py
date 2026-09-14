# Databricks notebook source
# MAGIC %md
# MAGIC # ChicagoPulse 03: Gold Metrics

# COMMAND ----------

CATALOG = spark.sql("SELECT current_catalog()").first()[0]
SCHEMA = "chicagopulse"

def exists(table):
    return spark.catalog.tableExists(
        f"{CATALOG}.{SCHEMA}.{table}"
    )

def gold(table, query):
    spark.sql(
        f"CREATE OR REPLACE TABLE `{CATALOG}`.`{SCHEMA}`.`{table}` AS {query}"
    )
    print(f"Built {CATALOG}.{SCHEMA}.{table}")

# COMMAND ----------

if exists("silver_311_service_requests"):
    gold(
        "gold_community_area_daily_metrics",
        f'''
        SELECT
            created_date AS metric_date,
            community_area,
            COUNT(*) AS service_request_count,
            SUM(
                CASE WHEN UPPER(status) LIKE '%OPEN%' THEN 1 ELSE 0 END
            ) AS open_request_count,
            SUM(
                CASE WHEN closed_at IS NOT NULL THEN 1 ELSE 0 END
            ) AS closed_request_count,
            COUNT(DISTINCT sr_type) AS distinct_service_types,
            AVG(
                CASE WHEN resolution_days >= 0 THEN resolution_days END
            ) AS avg_resolution_days
        FROM `{CATALOG}`.`{SCHEMA}`.`silver_311_service_requests`
        WHERE community_area BETWEEN 1 AND 77
          AND created_date IS NOT NULL
        GROUP BY created_date, community_area
        '''
    )

    gold(
        "gold_community_area_monthly_metrics",
        f'''
        WITH monthly AS (
            SELECT
                DATE_TRUNC('MONTH', created_date) AS metric_month,
                community_area,
                COUNT(*) AS service_request_count,
                SUM(
                    CASE WHEN UPPER(status) LIKE '%OPEN%' THEN 1 ELSE 0 END
                ) AS open_request_count,
                AVG(
                    CASE WHEN resolution_days >= 0 THEN resolution_days END
                ) AS avg_resolution_days
            FROM `{CATALOG}`.`{SCHEMA}`.`silver_311_service_requests`
            WHERE community_area BETWEEN 1 AND 77
              AND created_date IS NOT NULL
            GROUP BY DATE_TRUNC('MONTH', created_date), community_area
        ),
        lagged AS (
            SELECT
                *,
                LAG(service_request_count) OVER (
                    PARTITION BY community_area ORDER BY metric_month
                ) AS previous_month_request_count
            FROM monthly
        )
        SELECT
            *,
            CASE
                WHEN previous_month_request_count > 0
                THEN ROUND(
                    100.0 *
                    (service_request_count - previous_month_request_count)
                    / previous_month_request_count,
                    2
                )
            END AS request_count_mom_pct
        FROM lagged
        '''
    )

    gold(
        "gold_service_type_trends",
        f'''
        SELECT
            DATE_TRUNC('MONTH', created_date) AS metric_month,
            community_area,
            sr_type,
            COUNT(*) AS service_request_count
        FROM `{CATALOG}`.`{SCHEMA}`.`silver_311_service_requests`
        WHERE community_area BETWEEN 1 AND 77
          AND created_date IS NOT NULL
          AND sr_type IS NOT NULL
        GROUP BY
            DATE_TRUNC('MONTH', created_date),
            community_area,
            sr_type
        '''
    )
else:
    print("311 Silver table not found.")

# COMMAND ----------

if exists("silver_business_licenses"):
    gold(
        "gold_dim_community_area",
        f'''
        SELECT
            community_area,
            MAX(community_area_name) AS community_area_name
        FROM `{CATALOG}`.`{SCHEMA}`.`silver_business_licenses`
        WHERE community_area BETWEEN 1 AND 77
          AND community_area_name IS NOT NULL
        GROUP BY community_area
        '''
    )

    gold(
        "gold_business_activity",
        f'''
        SELECT
            DATE_TRUNC('MONTH', license_start_date) AS metric_month,
            community_area,
            COUNT(*) AS license_records,
            SUM(
                CASE WHEN application_type = 'ISSUE' THEN 1 ELSE 0 END
            ) AS new_license_issues,
            COUNT(DISTINCT account_number) AS distinct_business_accounts
        FROM `{CATALOG}`.`{SCHEMA}`.`silver_business_licenses`
        WHERE community_area BETWEEN 1 AND 77
          AND license_start_date IS NOT NULL
        GROUP BY
            DATE_TRUNC('MONTH', license_start_date),
            community_area
        '''
    )
else:
    print("Business licenses Silver table not found.")

# COMMAND ----------

if exists("silver_building_permits"):
    gold(
        "gold_building_activity",
        f'''
        SELECT
            DATE_TRUNC('MONTH', issue_date) AS metric_month,
            community_area,
            COUNT(*) AS permit_count,
            SUM(
                CASE
                    WHEN UPPER(permit_type) LIKE '%NEW CONSTRUCTION%'
                    THEN 1 ELSE 0
                END
            ) AS new_construction_permit_count,
            SUM(COALESCE(total_fee, 0)) AS total_permit_fees,
            AVG(processing_time_days) AS avg_processing_time_days
        FROM `{CATALOG}`.`{SCHEMA}`.`silver_building_permits`
        WHERE community_area BETWEEN 1 AND 77
          AND issue_date IS NOT NULL
        GROUP BY
            DATE_TRUNC('MONTH', issue_date),
            community_area
        '''
    )
else:
    print("Building permits Silver table not found.")

# COMMAND ----------

required = [
    "gold_community_area_monthly_metrics",
    "gold_dim_community_area",
    "gold_business_activity",
    "gold_building_activity",
]

if all(exists(table) for table in required):
    gold(
        "gold_neighborhood_pulse",
        f'''
        WITH business AS (
            SELECT
                *,
                LAG(new_license_issues) OVER (
                    PARTITION BY community_area ORDER BY metric_month
                ) AS previous_month_new_license_issues
            FROM `{CATALOG}`.`{SCHEMA}`.`gold_business_activity`
        )
        SELECT
            m.metric_month,
            m.community_area,
            d.community_area_name,
            m.service_request_count,
            m.previous_month_request_count,
            m.request_count_mom_pct,
            m.open_request_count,
            m.avg_resolution_days,
            b.new_license_issues,
            b.previous_month_new_license_issues,
            p.permit_count,
            p.new_construction_permit_count,
            p.total_permit_fees,
            CASE
                WHEN m.service_request_count >= 50
                 AND m.request_count_mom_pct >= 20
                THEN TRUE ELSE FALSE
            END AS complaints_rising_flag,
            CASE
                WHEN b.previous_month_new_license_issues > 0
                 AND b.new_license_issues
                     < b.previous_month_new_license_issues
                THEN TRUE ELSE FALSE
            END AS new_business_activity_declining_flag
        FROM `{CATALOG}`.`{SCHEMA}`.`gold_community_area_monthly_metrics` m
        LEFT JOIN `{CATALOG}`.`{SCHEMA}`.`gold_dim_community_area` d
          ON m.community_area = d.community_area
        LEFT JOIN business b
          ON m.metric_month = b.metric_month
         AND m.community_area = b.community_area
        LEFT JOIN `{CATALOG}`.`{SCHEMA}`.`gold_building_activity` p
          ON m.metric_month = p.metric_month
         AND m.community_area = p.community_area
        '''
    )
else:
    print(
        "gold_neighborhood_pulse requires 311, business licenses, "
        "and building permits."
    )

# COMMAND ----------

display(spark.sql(f"SHOW TABLES IN `{CATALOG}`.`{SCHEMA}`"))