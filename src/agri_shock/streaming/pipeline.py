"""Kafka-to-Delta Spark Structured Streaming transformations.

Imports are inside functions so package validation does not require Java/Spark.
"""
from __future__ import annotations
from typing import Any
from agri_shock.streaming.contracts import EventTimePolicy

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

def parse_mandi(kafka_df: Any, policy: EventTimePolicy) -> tuple[Any, Any]:
    from pyspark.sql import functions as F
    from pyspark.sql.types import DecimalType, StringType, StructField, StructType
    payload = StructType([StructField("state", StringType()), StructField("district", StringType()), StructField("market", StringType()), StructField("commodity", StringType()), StructField("variety", StringType()), StructField("min_price", DecimalType(18, 2)), StructField("modal_price", DecimalType(18, 2)), StructField("max_price", DecimalType(18, 2)), StructField("price_unit", StringType())])
    schema = StructType([StructField("event_id", StringType()), StructField("event_type", StringType()), StructField("event_time", StringType()), StructField("ingestion_time", StringType()), StructField("source", StringType()), StructField("schema_version", StringType()), StructField("payload", payload)])
    parsed = kafka_df.select("*", F.from_json("raw_json", schema).alias("event")).select("kafka_key", "raw_json", "topic", "partition", "offset", "kafka_timestamp", "event.*").withColumn("event_time", F.to_timestamp("event_time")).withColumn("ingestion_time", F.to_timestamp("ingestion_time"))
    valid_rule = (F.col("event_id").isNotNull() & F.col("event_time").isNotNull() & (F.length(F.trim("payload.district")) > 0) & (F.length(F.trim("payload.market")) > 0) & (F.length(F.trim("payload.commodity")) > 0) & (F.col("payload.min_price") >= 0) & (F.col("payload.min_price") <= F.col("payload.modal_price")) & (F.col("payload.modal_price") <= F.col("payload.max_price")))
    invalid = parsed.filter(~valid_rule)
    valid = (parsed.filter(valid_rule).withWatermark("event_time", policy.spark_duration).dropDuplicates(["event_id"]).select("event_id", "event_time", "ingestion_time", "source", "payload.*"))
    return valid, invalid

def daily_price_windows(valid_mandi: Any) -> Any:
    from pyspark.sql import functions as F
    return valid_mandi.groupBy(F.window("event_time", "1 day"), "state", "district", "market", "commodity").agg(F.avg("modal_price").alias("avg_modal_price"), F.count("*").alias("observation_count"))

def write_delta(stream_df: Any, path: str, checkpoint_path: str, query_name: str) -> Any:
    return (stream_df.writeStream.format("delta").outputMode("append").option("checkpointLocation", checkpoint_path).queryName(query_name).start(path))
