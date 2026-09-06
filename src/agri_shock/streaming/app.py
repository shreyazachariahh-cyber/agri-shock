"""Runnable Kafka → Delta Structured Streaming application.

Run in the documented Python 3.11 / Java 17 environment:
    python -m agri_shock.streaming.app
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from agri_shock.common.config import Settings
from agri_shock.common.logging import configure_logging
from agri_shock.streaming.contracts import EventTimePolicy
from agri_shock.streaming.pipeline import bronze_events, kafka_input, parse_mandi, write_delta
from agri_shock.geospatial.spark import canonicalize_markets, flood_shocks, weather_shocks
from agri_shock.streaming.joins import ShockJoinPolicy, join_shocks_to_prices

KAFKA_PACKAGE = "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.6"
SEDONA_PACKAGE = "org.apache.sedona:sedona-spark-shaded-3.5_2.12:1.9.0"


def create_streaming_spark(app_name: str = "agrishock-streaming") -> Any:
    try:
        from delta import configure_spark_with_delta_pip
        from pyspark.sql import SparkSession
    except ImportError as error:
        raise RuntimeError("Install agri-shock[streaming] in Python 3.11 and configure Java 17") from error
    builder = (SparkSession.builder.appName(app_name)
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
        .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog"))
    spark = configure_spark_with_delta_pip(builder, extra_packages=[KAFKA_PACKAGE, SEDONA_PACKAGE]).getOrCreate()
    from sedona.spark import SedonaContext
    SedonaContext.create(spark)
    return spark


def parse_simple_event(kafka_df: Any, payload_schema: Any, required_payload_fields: list[str], policy: EventTimePolicy) -> tuple[Any, Any]:
    """Parse a source-specific envelope and return validated/invalid streams."""
    from pyspark.sql import functions as F
    from pyspark.sql.types import StringType, StructField, StructType
    schema = StructType([
        StructField("event_id", StringType()), StructField("event_type", StringType()),
        StructField("event_time", StringType()), StructField("ingestion_time", StringType()),
        StructField("source", StringType()), StructField("schema_version", StringType()),
        StructField("payload", payload_schema),
    ])
    parsed = (kafka_df.select("*", F.from_json("raw_json", schema).alias("event"))
        .select("kafka_key", "raw_json", "topic", "partition", "offset", "kafka_timestamp", "event.*")
        .withColumn("event_time", F.to_timestamp("event_time"))
        .withColumn("ingestion_time", F.to_timestamp("ingestion_time")))
    valid = F.col("event_id").isNotNull() & F.col("event_time").isNotNull()
    for field in required_payload_fields:
        valid = valid & (F.length(F.trim(F.col(f"payload.{field}"))) > 0)
    invalid = parsed.filter(~valid)
    return (parsed.filter(valid).withWatermark("event_time", policy.spark_duration)
        .dropDuplicates(["event_id"]).select(
            "event_id", "event_time", "ingestion_time", "source", "schema_version",
            F.col("topic").alias("kafka_topic"), F.col("partition").alias("kafka_partition"),
            F.col("offset").alias("kafka_offset"), "kafka_timestamp",
            F.col("raw_json").alias("raw_payload"), "payload.*",
        ), invalid)


def start_dlq(invalid_stream: Any, settings: Settings, checkpoint_path: str) -> Any:
    from pyspark.sql import functions as F
    envelope = invalid_stream.select(
        F.sha2("raw_json", 256).alias("event_id"), F.lit("dead_letter_event").alias("event_type"),
        F.coalesce("event_time", "kafka_timestamp").alias("event_time"), F.current_timestamp().alias("ingestion_time"),
        F.lit("agrishock_spark").alias("source"), F.lit("1.0").alias("schema_version"),
        F.struct(F.lit("spark_validation").alias("stage"), F.lit("schema_or_semantic_validation_failed").alias("reason"), "raw_json", "topic", "partition", "offset").alias("payload"),
    ).selectExpr("CAST(event_id AS STRING) AS key", "to_json(struct(*)) AS value")
    return (envelope.writeStream.format("kafka").option("kafka.bootstrap.servers", settings.kafka_bootstrap_servers)
        .option("topic", "dead-letter-events").option("checkpointLocation", checkpoint_path).outputMode("append").queryName("agrishock-dlq").start())


def start_application(settings: Settings) -> list[Any]:
    if settings.watermark_hours is None:
        raise ValueError("WATERMARK_HOURS must be explicitly configured before starting Spark")
    if settings.shock_lookahead_days is None:
        raise ValueError("SHOCK_LOOKAHEAD_DAYS must be explicitly configured before starting Spark")
    if settings.market_dimension_path is None or settings.district_boundary_path is None:
        raise ValueError("MARKET_DIMENSION_PATH and DISTRICT_BOUNDARY_PATH are required for geographic association")
    policy = EventTimePolicy(settings.watermark_hours)
    spark = create_streaming_spark()
    root, checkpoints = Path(settings.delta_root), Path(settings.checkpoint_root)
    mandi_raw = kafka_input(spark, settings.kafka_bootstrap_servers, "mandi-prices")
    weather_raw = kafka_input(spark, settings.kafka_bootstrap_servers, "weather-events")
    flood_raw = kafka_input(spark, settings.kafka_bootstrap_servers, "flood-events")
    raw_events = mandi_raw.unionByName(weather_raw).unionByName(flood_raw)
    bronze = bronze_events(raw_events)
    queries = [write_delta(
        bronze, str(root / "bronze" / "raw_events"), str(checkpoints / "bronze_raw"),
        "agrishock-bronze-raw", ["kafka_topic", "source_event_date"],
    )]
    mandi, mandi_invalid = parse_mandi(mandi_raw, policy)
    queries.append(write_delta(
        mandi, str(root / "silver" / "mandi_prices"), str(checkpoints / "silver_mandi"),
        "agrishock-silver-mandi", ["source"],
    ))
    from pyspark.sql.types import DecimalType, StringType, StructField, StructType
    weather_payload = StructType([StructField("state", StringType()), StructField("district", StringType()), StructField("rainfall_actual_mm", DecimalType(12, 2)), StructField("rainfall_normal_mm", DecimalType(12, 2)), StructField("rainfall_departure_pct", DecimalType(12, 2)), StructField("rainfall_category", StringType()), StructField("imd_object_id", StringType())])
    flood_payload = StructType([StructField("source_event_id", StringType()), StructField("event_start", StringType()), StructField("event_end", StringType()), StructField("alert_level", StringType()), StructField("geometry_json", StringType())])
    weather, weather_invalid = parse_simple_event(weather_raw, weather_payload, ["district", "rainfall_category"], policy)
    flood, flood_invalid = parse_simple_event(flood_raw, flood_payload, ["source_event_id"], policy)
    queries.extend([
        write_delta(weather, str(root / "silver" / "weather_events"), str(checkpoints / "silver_weather"), "agrishock-silver-weather", ["source"]),
        write_delta(flood, str(root / "silver" / "flood_events"), str(checkpoints / "silver_flood"), "agrishock-silver-flood", ["source"]),
        start_dlq(mandi_invalid.unionByName(weather_invalid, allowMissingColumns=True).unionByName(flood_invalid, allowMissingColumns=True), settings, str(checkpoints / "dlq")),
    ])
    market_dimension = spark.read.format("delta").load(settings.market_dimension_path)
    district_boundaries = spark.read.format("delta").load(settings.district_boundary_path)
    market_resolution = canonicalize_markets(mandi, market_dimension)
    canonical_prices = market_resolution.filter("mapping_status = 'resolved'")
    unresolved_markets = market_resolution.filter("mapping_status = 'unresolved'")
    queries.append(write_delta(
        unresolved_markets, str(root / "silver" / "unresolved_market_mappings"),
        str(checkpoints / "silver_unresolved_market_mappings"),
        "agrishock-silver-unresolved-market-mappings", ["source"],
    ))
    shocks = weather_shocks(weather, district_boundaries).unionByName(flood_shocks(flood, district_boundaries))
    associations = join_shocks_to_prices(shocks, canonical_prices, ShockJoinPolicy(settings.shock_lookahead_days))
    queries.append(write_delta(
        associations, str(root / "gold" / "shock_price_associations"),
        str(checkpoints / "gold_associations"), "agrishock-gold-associations",
        ["shock_type"],
    ))
    return queries


def main() -> None:
    configure_logging(os.getenv("LOG_LEVEL", "INFO"))
    queries = start_application(Settings.from_environment())
    try:
        queries[0].awaitTermination()
    finally:
        for query in queries:
            if query.isActive:
                query.stop()


if __name__ == "__main__":
    main()
