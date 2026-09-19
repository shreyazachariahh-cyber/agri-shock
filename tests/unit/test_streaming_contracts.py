import pytest
from agri_shock.streaming.contracts import (
    DLQ_DELTA_CHECKPOINT_NAME,
    DLQ_DELTA_RELATIVE_PATH,
    DLQ_ENVELOPE_FIELDS,
    EventTimePolicy,
    dead_letter_event_id,
)

def test_watermark_requires_explicit_positive_duration() -> None:
    assert EventTimePolicy(72).spark_duration == "72 hours"
    with pytest.raises(ValueError):
        EventTimePolicy(0)


def test_dead_letter_identity_rejects_invalid_kafka_coordinates() -> None:
    with pytest.raises(ValueError, match="Kafka topic"):
        dead_letter_event_id("", 0, 0, "{}")


def test_dlq_contract_has_durable_path_independent_checkpoint_and_full_envelope() -> None:
    assert DLQ_DELTA_RELATIVE_PATH == "silver/dlq_events"
    assert DLQ_DELTA_CHECKPOINT_NAME == "dlq_delta"
    assert DLQ_ENVELOPE_FIELDS == (
        "event_id", "event_type", "event_time", "ingestion_time", "source", "schema_version", "payload",
    )
