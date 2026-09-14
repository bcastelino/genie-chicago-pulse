# Databricks notebook source
# MAGIC %md
# MAGIC # ChicagoPulse 06: Community Area Boundaries
# MAGIC
# MAGIC This notebook loads the official City of Chicago Community Area boundary dataset,
# MAGIC canonicalizes all 77 Community Area names using Community Area number as the key,
# MAGIC validates the polygons, and recreates:
# MAGIC
# MAGIC `<catalog>.chicagopulse.silver_community_area_boundaries`
# MAGIC
# MAGIC `<catalog>.chicagopulse.gold_dim_community_area`
# MAGIC
# MAGIC This permanently protects names such as `O'Hare` and `McKinley Park` from generic
# MAGIC title-casing logic.
# MAGIC
# MAGIC Do not replace the canonical mapping with `INITCAP(LOWER(...))`.

# COMMAND ----------

import json
import urllib.request
from datetime import datetime, timezone

from pyspark.sql import functions as F
from pyspark.sql.types import (
    IntegerType,
    StringType,
    StructField,
    StructType,
)

CATALOG = spark.sql("SELECT current_catalog()").first()[0]
SCHEMA = "chicagopulse"

DATASET_ID = "igwz-8jzy"
SOURCE_URL = (
    "https://data.cityofchicago.org/"
    "api/v3/views/igwz-8jzy/query.geojson?accessType=DOWNLOAD"
)

def fq(table):
    return f"`{CATALOG}`.`{SCHEMA}`.`{table}`"

print("Namespace:", f"{CATALOG}.{SCHEMA}")
print("Community Area source:", DATASET_ID)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Canonical names
# MAGIC
# MAGIC Community Area number is the stable key.
# MAGIC
# MAGIC Using the complete mapping avoids casing issues during future boundary refreshes.

# COMMAND ----------

CANONICAL_COMMUNITY_AREAS = {
    1: "Rogers Park",
    2: "West Ridge",
    3: "Uptown",
    4: "Lincoln Square",
    5: "North Center",
    6: "Lake View",
    7: "Lincoln Park",
    8: "Near North Side",
    9: "Edison Park",
    10: "Norwood Park",
    11: "Jefferson Park",
    12: "Forest Glen",
    13: "North Park",
    14: "Albany Park",
    15: "Portage Park",
    16: "Irving Park",
    17: "Dunning",
    18: "Montclare",
    19: "Belmont Cragin",
    20: "Hermosa",
    21: "Avondale",
    22: "Logan Square",
    23: "Humboldt Park",
    24: "West Town",
    25: "Austin",
    26: "West Garfield Park",
    27: "East Garfield Park",
    28: "Near West Side",
    29: "North Lawndale",
    30: "South Lawndale",
    31: "Lower West Side",
    32: "Loop",
    33: "Near South Side",
    34: "Armour Square",
    35: "Douglas",
    36: "Oakland",
    37: "Fuller Park",
    38: "Grand Boulevard",
    39: "Kenwood",
    40: "Washington Park",
    41: "Hyde Park",
    42: "Woodlawn",
    43: "South Shore",
    44: "Chatham",
    45: "Avalon Park",
    46: "South Chicago",
    47: "Burnside",
    48: "Calumet Heights",
    49: "Roseland",
    50: "Pullman",
    51: "South Deering",
    52: "East Side",
    53: "West Pullman",
    54: "Riverdale",
    55: "Hegewisch",
    56: "Garfield Ridge",
    57: "Archer Heights",
    58: "Brighton Park",
    59: "McKinley Park",
    60: "Bridgeport",
    61: "New City",
    62: "West Elsdon",
    63: "Gage Park",
    64: "Clearing",
    65: "West Lawn",
    66: "Chicago Lawn",
    67: "West Englewood",
    68: "Englewood",
    69: "Greater Grand Crossing",
    70: "Ashburn",
    71: "Auburn Gresham",
    72: "Beverly",
    73: "Washington Heights",
    74: "Mount Greenwood",
    75: "Morgan Park",
    76: "O'Hare",
    77: "Edgewater",
}

assert len(CANONICAL_COMMUNITY_AREAS) == 77
assert set(CANONICAL_COMMUNITY_AREAS.keys()) == set(range(1, 78))

print("Canonical Community Area mapping validated.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Download official GeoJSON

# COMMAND ----------

request = urllib.request.Request(
    SOURCE_URL,
    headers={
        "User-Agent": "ChicagoPulse-Databricks-Free-Edition/1.0",
        "Accept": "application/geo+json, application/json",
    },
)

with urllib.request.urlopen(request, timeout=120) as response:
    geojson = json.loads(response.read().decode("utf-8"))

if geojson.get("type") != "FeatureCollection":
    raise RuntimeError(
        f"Unexpected GeoJSON type: {geojson.get('type')}"
    )

features = geojson.get("features", [])

if len(features) != 77:
    raise RuntimeError(
        "Expected exactly 77 Community Area polygons, "
        f"but the source returned {len(features)}."
    )

print("Downloaded Community Area polygons:", len(features))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Parse source fields
# MAGIC
# MAGIC The source has historically used fields such as `area_numbe` and `community`.
# MAGIC This parser accepts a small set of aliases but always uses our canonical name mapping.

# COMMAND ----------

NUMBER_CANDIDATES = [
    "area_numbe",
    "area_num_1",
    "area_num",
    "area_number",
    "community_area",
    "community_area_number",
]

NAME_CANDIDATES = [
    "community",
    "community_area_name",
    "name",
]

def first_present(properties, candidates):
    lowered = {
        str(key).lower(): value
        for key, value in properties.items()
    }

    for candidate in candidates:
        if candidate.lower() in lowered:
            return lowered[candidate.lower()]

    return None


rows = []
ingested_at = datetime.now(timezone.utc).isoformat()

for feature in features:
    properties = feature.get("properties") or {}
    geometry = feature.get("geometry")

    raw_number = first_present(
        properties,
        NUMBER_CANDIDATES,
    )

    raw_name = first_present(
        properties,
        NAME_CANDIDATES,
    )

    if raw_number is None:
        raise RuntimeError(
            "Community Area number not found. "
            f"Available source fields: {sorted(properties.keys())}"
        )

    try:
        community_area = int(float(str(raw_number)))
    except Exception as exc:
        raise RuntimeError(
            f"Invalid Community Area number: {raw_number}"
        ) from exc

    if community_area not in CANONICAL_COMMUNITY_AREAS:
        raise RuntimeError(
            f"Unexpected Community Area number: {community_area}"
        )

    if geometry is None:
        raise RuntimeError(
            f"Community Area {community_area} has no geometry."
        )

    rows.append(
        (
            community_area,
            CANONICAL_COMMUNITY_AREAS[community_area],
            str(raw_name) if raw_name is not None else None,
            json.dumps(
                geometry,
                separators=(",", ":"),
            ),
            DATASET_ID,
            ingested_at,
        )
    )

print("Parsed boundary rows:", len(rows))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Create and validate the boundary DataFrame

# COMMAND ----------

schema = StructType(
    [
        StructField(
            "community_area",
            IntegerType(),
            False,
        ),
        StructField(
            "community_area_name",
            StringType(),
            False,
        ),
        StructField(
            "source_community_area_name",
            StringType(),
            True,
        ),
        StructField(
            "geometry_geojson",
            StringType(),
            False,
        ),
        StructField(
            "_source_dataset_id",
            StringType(),
            False,
        ),
        StructField(
            "_ingested_at",
            StringType(),
            False,
        ),
    ]
)

boundaries = (
    spark.createDataFrame(
        rows,
        schema=schema,
    )
    .withColumn(
        "_ingested_at",
        F.to_timestamp("_ingested_at"),
    )
)

summary = boundaries.agg(
    F.count("*").alias("row_count"),
    F.countDistinct("community_area").alias(
        "distinct_community_areas"
    ),
    F.countDistinct("community_area_name").alias(
        "distinct_names"
    ),
    F.sum(
        F.when(
            F.col("geometry_geojson").isNull(),
            1,
        ).otherwise(0)
    ).alias("missing_geometry"),
).first()

assert summary["row_count"] == 77
assert summary["distinct_community_areas"] == 77
assert summary["distinct_names"] == 77
assert summary["missing_geometry"] == 0

display(
    boundaries.orderBy("community_area")
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Explicit regression checks for names that generic title-casing can damage

# COMMAND ----------

expected_special_names = {
    59: "McKinley Park",
    76: "O'Hare",
}

actual_special_names = {
    row["community_area"]: row["community_area_name"]
    for row in (
        boundaries
        .filter(
            F.col("community_area").isin(
                list(expected_special_names.keys())
            )
        )
        .select(
            "community_area",
            "community_area_name",
        )
        .collect()
    )
}

assert actual_special_names == expected_special_names, (
    "Canonical-name regression detected: "
    f"{actual_special_names}"
)

display(
    boundaries
    .filter(
        F.col("community_area").isin(59, 76)
    )
    .select(
        "community_area",
        "community_area_name",
        "source_community_area_name",
    )
    .orderBy("community_area")
)

print("59 = McKinley Park")
print("76 = O'Hare")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Validate polygon parsing in Databricks

# COMMAND ----------

geometry_validation = boundaries.selectExpr(
    "community_area",
    "ST_GEOMFROMGEOJSON(geometry_geojson) IS NOT NULL AS geometry_valid",
)

invalid_geometry_count = (
    geometry_validation
    .filter(~F.col("geometry_valid"))
    .count()
)

if invalid_geometry_count != 0:
    raise RuntimeError(
        f"{invalid_geometry_count} invalid Community Area geometries found."
    )

print("All 77 GeoJSON polygons parsed successfully.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Write Silver boundary table

# COMMAND ----------

(
    boundaries
    .write
    .format("delta")
    .mode("overwrite")
    .option(
        "overwriteSchema",
        "true",
    )
    .saveAsTable(
        f"{CATALOG}.{SCHEMA}.silver_community_area_boundaries"
    )
)

spark.sql(
    f"""
    COMMENT ON TABLE
        {fq("silver_community_area_boundaries")}
    IS
        'Official City of Chicago Community Area polygons with canonical '
        'Community Area names. Used by ChicagoPulse spatial enrichment.'
    """
)

print(
    "Created",
    f"{CATALOG}.{SCHEMA}.silver_community_area_boundaries",
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Create Gold Community Area dimension
# MAGIC
# MAGIC The GeoJSON polygon is retained for the future ChicagoPulse frontend map.

# COMMAND ----------

spark.sql(
    f"""
    CREATE OR REPLACE TABLE
        {fq("gold_dim_community_area")}
    AS
    SELECT
        community_area,
        community_area_name,
        geometry_geojson,
        _source_dataset_id,
        _ingested_at
    FROM
        {fq("silver_community_area_boundaries")}
    """
)

spark.sql(
    f"""
    COMMENT ON TABLE
        {fq("gold_dim_community_area")}
    IS
        'Canonical dimension for Chicago''s 77 official Community Areas, '
        'including official polygon geometry for analytics and app mapping.'
    """
)

print(
    "Created",
    f"{CATALOG}.{SCHEMA}.gold_dim_community_area",
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Final validation

# COMMAND ----------

final_rows = (
    spark.table(
        f"{CATALOG}.{SCHEMA}.gold_dim_community_area"
    )
    .select(
        "community_area",
        "community_area_name",
    )
    .orderBy("community_area")
    .collect()
)

final_names = {
    row["community_area"]: row["community_area_name"]
    for row in final_rows
}

assert len(final_rows) == 77
assert len(final_names) == 77
assert final_names[59] == "McKinley Park"
assert final_names[76] == "O'Hare"

display(
    spark.table(
        f"{CATALOG}.{SCHEMA}.gold_dim_community_area"
    )
    .filter(
        F.col("community_area").isin(59, 76)
    )
    .select(
        "community_area",
        "community_area_name",
    )
    .orderBy("community_area")
)

print("ChicagoPulse Notebook 06 PASSED")
print("77 canonical Community Areas loaded.")
print("59 = McKinley Park")
print("76 = O'Hare")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Refresh guidance
# MAGIC
# MAGIC This notebook is not part of the daily Lakeflow Job.
# MAGIC
# MAGIC Re-run it only when the City publishes a Community Area boundary update or during
# MAGIC an occasional maintenance check.
# MAGIC
# MAGIC If polygon geometry changes, rerun the Building Violation spatial enrichment afterward.