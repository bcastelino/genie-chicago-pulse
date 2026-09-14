# Databricks notebook source
# MAGIC %md
# MAGIC # ChicagoPulse 07: Building Violation Spatial Enrichment
# MAGIC
# MAGIC Maps each Building Violation latitude/longitude point to one of Chicago's official Community Area polygons.
# MAGIC
# MAGIC Output:
# MAGIC
# MAGIC `<catalog>.chicagopulse.silver_building_violations_enriched`

# COMMAND ----------

CATALOG=spark.sql("SELECT current_catalog()").first()[0]
SCHEMA="chicagopulse"

VIOLATIONS="silver_building_violations"
BOUNDARIES="silver_community_area_boundaries"
OUTPUT="silver_building_violations_enriched"

def exists(table):
    return spark.catalog.tableExists(f"{CATALOG}.{SCHEMA}.{table}")

assert exists(VIOLATIONS),"silver_building_violations is missing"
assert exists(BOUNDARIES),"Run notebook 06 first"

# COMMAND ----------

spark.sql(f'''
CREATE OR REPLACE TABLE `{CATALOG}`.`{SCHEMA}`.`{OUTPUT}` AS
SELECT
    v.*,
    c.community_area,
    c.community_area_name,
    CASE
        WHEN v.latitude IS NULL OR v.longitude IS NULL
            THEN 'MISSING_COORDINATES'
        WHEN c.community_area IS NOT NULL
            THEN 'MATCHED'
        ELSE 'OUTSIDE_OR_UNMATCHED'
    END AS geography_match_status
FROM `{CATALOG}`.`{SCHEMA}`.`{VIOLATIONS}` v
LEFT JOIN `{CATALOG}`.`{SCHEMA}`.`{BOUNDARIES}` c
  ON v.latitude IS NOT NULL
 AND v.longitude IS NOT NULL
 AND ST_COVERS(
        ST_GEOMFROMGEOJSON(c.geometry_geojson),
        ST_POINT(v.longitude,v.latitude,4326)
     )
''')

print(f"Built {CATALOG}.{SCHEMA}.{OUTPUT}")

# COMMAND ----------

display(spark.sql(f'''
SELECT
    geography_match_status,
    COUNT(*) AS rows,
    ROUND(100.0*COUNT(*)/SUM(COUNT(*)) OVER (),2) AS pct
FROM `{CATALOG}`.`{SCHEMA}`.`{OUTPUT}`
GROUP BY geography_match_status
ORDER BY rows DESC
'''))

# COMMAND ----------

display(spark.sql(f'''
SELECT
    community_area,
    community_area_name,
    COUNT(*) AS violation_count
FROM `{CATALOG}`.`{SCHEMA}`.`{OUTPUT}`
WHERE geography_match_status='MATCHED'
GROUP BY community_area,community_area_name
ORDER BY violation_count DESC
LIMIT 20
'''))