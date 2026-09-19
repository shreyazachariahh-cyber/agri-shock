"""Kafka-to-Delta Spark Structured Streaming transformations.

Imports are inside functions so package validation does not require Java/Spark.
"""
from __future__ import annotations
from typing import Any
from agri_shock.streaming.contracts import EventTimePolicy


ADDITIVE_SCHEMA_EVOLUTION_SINKS = frozenset({"agrishock-silver-unresolved-market-mappings"})

def create_spark(app_name: str = "agrishock-streaming") -> Any:
    try:
        from pyspark.sql import SparkSession
    except ImportError as error:
        raise RuntimeError("Install agri-shock[streaming] and provide Java 17+ to run Spark") from error
    return (SparkSession.builder.appName(app_name)
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
        .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog")
        .getOrCreate())

def kafka_input(spark: Any, bootstrap_servers: str, topic: str) -> Any:
    return (spark.readStream.format("kafka").option("kafka.bootstrap.servers", bootstrap_servers)
        .option("subscribe", topic).option("startingOffsets", "earliest").load()
        .selectExpr("CAST(key AS STRING) AS kafka_key", "CAST(value AS STRING) AS raw_json", "topic", "partition", "offset", "timestamp AS kafka_timestamp"))


def bronze_events(kafka_df: Any) -> Any:
    """Capture immutable Kafka records before parsing or deduplication.

    Raw payload and Kafka coordinates make the record debuggable and replayable;
    extracted envelope fields are metadata only and never replace raw JSON.
    """
    from pyspark.sql import functions as F

    source_event_time = F.to_timestamp(F.get_json_object("raw_json", "$.event_time"))
    return kafka_df.select(
        F.col("raw_json").alias("raw_payload"),
        F.col("kafka_key"),
        F.col("topic").alias("kafka_topic"),
        F.col("partition").alias("kafka_partition"),
        F.col("offset").alias("kafka_offset"),
        F.col("kafka_timestamp"),
        F.current_timestamp().alias("bronze_ingestion_time"),
        source_event_time.alias("source_event_time"),
        F.get_json_object("raw_json", "$.event_id").alias("source_event_id"),
        F.get_json_object("raw_json", "$.event_type").alias("source_event_type"),
        F.get_json_object("raw_json", "$.source").alias("source"),
        F.get_json_object("raw_json", "$.schema_version").alias("source_schema_version"),
        F.to_date(source_event_time).alias("source_event_date"),
    )

def parse_mandi(kafka_df: Any, policy: EventTimePolicy) -> tuple[Any, Any]:
    from pyspark.sql import functions as F
    from pyspark.sql.types import DecimalType, StringType, StructField, StructType
    payload = StructType([StructField("state", StringType()), StructField("district", StringType()), StructField("market", StringType()), StructField("commodity", StringType()), StructField("variety", StringType()), StructField("min_price", DecimalType(18, 2)), StructField("modal_price", DecimalType(18, 2)), StructField("max_price", DecimalType(18, 2)), StructField("price_unit", StringType())])
    schema = StructType([StructField("event_id", StringType()), StructField("event_type", StringType()), StructField("event_time", StringType()), StructField("ingestion_time", StringType()), StructField("source", StringType()), StructField("schema_version", StringType()), StructField("payload", payload)])
    parsed = kafka_df.select("*", F.from_json("raw_json", schema).alias("event")).select("kafka_key", "raw_json", "topic", "partition", "offset", "kafka_timestamp", F.col("event").isNull().alias("_malformed_json"), "event.*").withColumn("event_time", F.to_timestamp("event_time")).withColumn("ingestion_time", F.to_timestamp("ingestion_time"))
    valid_rule = (F.col("event_id").isNotNull() & F.col("event_time").isNotNull() & (F.length(F.trim("payload.district")) > 0) & (F.length(F.trim("payload.market")) > 0) & (F.length(F.trim("payload.commodity")) > 0) & (F.col("payload.min_price") >= 0) & (F.col("payload.min_price") <= F.col("payload.modal_price")) & (F.col("payload.modal_price") <= F.col("payload.max_price")))
    invalid = parsed.filter(~valid_rule).withColumn(
        "_dlq_reason",
        F.when(F.col("_malformed_json"), F.lit("malformed_json"))
        .when(F.col("event_id").isNull(), F.lit("missing_event_id"))
        .when(F.col("event_time").isNull(), F.lit("invalid_event_time"))
        .otherwise(F.lit("mandi_schema_or_price_validation_failed")),
    )
    valid = (parsed.filter(valid_rule).withWatermark("event_time", policy.spark_duration).dropDuplicates(["event_id"]).select(
        "event_id", "event_time", "ingestion_time", "source", "schema_version",
        F.col("topic").alias("kafka_topic"), F.col("partition").alias("kafka_partition"),
        F.col("offset").alias("kafka_offset"), "kafka_timestamp",
        F.col("raw_json").alias("raw_payload"), "payload.*",
    ))
    return valid, invalid

def daily_price_windows(valid_mandi: Any) -> Any:
    from pyspark.sql import functions as F
    return valid_mandi.groupBy(F.window("event_time", "1 day"), "state", "district", "market", "commodity").agg(F.avg("modal_price").alias("avg_modal_price"), F.count("*").alias("observation_count"))

def write_delta(
    stream_df: Any,
    path: str,
    checkpoint_path: str,
    query_name: str,
    partition_by: list[str] | None = None,
    allow_additive_schema_evolution: bool = False,
) -> Any:
    """Write only Delta with a deterministic checkpoint per materialized table.

    Structured Streaming checkpoints plus Delta transaction logs provide replay
    safety for a stable query/checkpoint pair. This is not a blanket claim of
    exactly-once behaviour across arbitrary checkpoint deletion or source
    corrections.
    """
    if allow_additive_schema_evolution and query_name not in ADDITIVE_SCHEMA_EVOLUTION_SINKS:
        raise ValueError(f"additive schema evolution is not approved for {query_name}")
    writer = (stream_df.writeStream.format("delta").outputMode("append")
        .option("checkpointLocation", checkpoint_path).queryName(query_name))
    if allow_additive_schema_evolution:
        writer = writer.option("mergeSchema", "true")
    if partition_by:
        writer = writer.partitionBy(*partition_by)
    return writer.start(path)
