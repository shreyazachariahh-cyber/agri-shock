"""Generic Spark/Sedona geographic normalization and shock construction."""
from __future__ import annotations
from typing import Any

def canonicalize_markets(prices: Any, market_dimension: Any) -> Any:
    """Resolve source market fields through an explicit curated reference table.

    Unresolved records remain visible with `mapping_status=unresolved`; callers
    must route them to a quality/reconciliation table instead of guessing IDs.
    """
    from pyspark.sql import functions as F
    normalized = prices.select("*", F.upper(F.trim("state")).alias("_source_state"), F.upper(F.trim("district")).alias("_source_district"), F.upper(F.trim("market")).alias("_source_market"))
    reference = market_dimension.select("market_id", "district_id", "state_id", F.upper(F.trim("source_state")).alias("_source_state"), F.upper(F.trim("source_district")).alias("_source_district"), F.upper(F.trim("source_market")).alias("_source_market"))
    return (normalized.join(reference, ["_source_state", "_source_district", "_source_market"], "left")
        .drop("_source_state", "_source_district", "_source_market")
        .withColumn("commodity_id", F.sha2(F.upper(F.trim("commodity")), 256))
        .withColumn("mapping_status", F.when(F.col("market_id").isNull(), F.lit("unresolved")).otherwise(F.lit("resolved"))))

def flood_shocks(floods: Any, district_boundaries: Any) -> Any:
    """Spatially associate GeoJSON flood geometry to canonical districts."""
    from pyspark.sql import functions as F
    flood_geometry = floods.filter(F.col("geometry_json").isNotNull()).withColumn("_flood_geometry", F.expr("ST_GeomFromGeoJSON(geometry_json)"))
    districts = district_boundaries.select("district_id", F.expr("ST_GeomFromGeoJSON(geometry_json)").alias("_district_geometry"))
    return flood_geometry.join(districts, F.expr("ST_Intersects(_flood_geometry, _district_geometry)"), "inner").select(F.col("event_id").alias("shock_id"), F.lit("flood").alias("shock_type"), F.col("event_time").alias("shock_time"), "district_id", F.lit("same_district").alias("spatial_relationship"), F.lit(None).cast("double").alias("shock_severity"), F.col("source_event_id").alias("source_reference"))

def weather_shocks(weather: Any, district_boundaries: Any) -> Any:
    """Map district weather observations using the same curated boundary reference."""
    from pyspark.sql import functions as F
    reference = district_boundaries.select("district_id", F.upper(F.trim("source_state")).alias("_source_state"), F.upper(F.trim("source_district")).alias("_source_district"))
    observations = weather.select("*", F.upper(F.trim("state")).alias("_source_state"), F.upper(F.trim("district")).alias("_source_district"))
    return observations.join(reference, ["_source_state", "_source_district"], "inner").select(F.col("event_id").alias("shock_id"), F.lit("rainfall_anomaly").alias("shock_type"), F.col("event_time").alias("shock_time"), "district_id", F.lit("same_district").alias("spatial_relationship"), F.least(F.lit(1.0), F.greatest(F.lit(0.0), F.col("rainfall_departure_pct") / F.lit(100.0))).alias("shock_severity"), F.col("imd_object_id").alias("source_reference"))
