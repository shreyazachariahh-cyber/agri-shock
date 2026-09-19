import pytest
from agri_shock.streaming.contracts import (
    DLQ_DELTA_CHECKPOINT_NAME,
    DLQ_DELTA_RELATIVE_PATH,
    DLQ_ENVELOPE_FIELDS,
    EventTimePolicy,
    dead_letter_event_id,
)
from agri_shock.streaming.pipeline import ADDITIVE_SCHEMA_EVOLUTION_SINKS, write_delta

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


def test_only_existing_unresolved_market_sink_is_approved_for_additive_schema_evolution() -> None:
    assert ADDITIVE_SCHEMA_EVOLUTION_SINKS == {"agrishock-silver-unresolved-market-mappings"}


def test_unresolved_market_sink_uses_explicit_additive_delta_schema_option() -> None:
    class Writer:
        def __init__(self) -> None:
            self.options: dict[str, str] = {}

        def format(self, _: str): return self
        def outputMode(self, _: str): return self
        def option(self, key: str, value: str): self.options[key] = value; return self
        def queryName(self, _: str): return self
        def partitionBy(self, *_: str): return self
        def start(self, _: str): return "query"

    writer = Writer()
    stream = type("Stream", (), {"writeStream": writer})()
    assert write_delta(stream, "path", "checkpoint", "agrishock-silver-unresolved-market-mappings", allow_additive_schema_evolution=True) == "query"
    assert writer.options["mergeSchema"] == "true"
    with pytest.raises(ValueError, match="not approved"):
        write_delta(stream, "path", "checkpoint", "agrishock-silver-mandi", allow_additive_schema_evolution=True)
