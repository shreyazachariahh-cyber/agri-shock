"""Streaming policy contracts that can be tested without a Spark runtime."""
from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256


DLQ_DELTA_RELATIVE_PATH = "silver/dlq_events"
DLQ_DELTA_CHECKPOINT_NAME = "dlq_delta"
DLQ_ENVELOPE_FIELDS = (
    "event_id", "event_type", "event_time", "ingestion_time", "source",
    "schema_version", "payload",
)

@dataclass(frozen=True, slots=True)
class EventTimePolicy:
    watermark_hours: int

    def __post_init__(self) -> None:
        if self.watermark_hours <= 0:
            raise ValueError("watermark_hours must be positive and evidence-based")

    @property
    def spark_duration(self) -> str:
        return f"{self.watermark_hours} hours"


def dead_letter_event_id(
    kafka_topic: str,
    kafka_partition: int,
    kafka_offset: int,
    raw_payload: str,
) -> str:
    """Stable identity for one rejected Kafka record, not merely its payload."""
    if not kafka_topic or kafka_partition < 0 or kafka_offset < 0:
        raise ValueError("Kafka topic, partition, and offset are required for DLQ identity")
    material = f"{kafka_topic}|{kafka_partition}|{kafka_offset}|{raw_payload}"
    return f"dlq:{sha256(material.encode('utf-8')).hexdigest()}"
