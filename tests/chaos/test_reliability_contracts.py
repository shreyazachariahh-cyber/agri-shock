"""Failure and replay contracts that run without Kafka, Spark, or Elasticsearch."""
from __future__ import annotations

from pathlib import Path

import pytest

from agri_shock.ingestion.base import RetryPolicy
from agri_shock.ingestion.mandi_producer import MandiProducer
from agri_shock.ingestion.publisher import MemoryPublisher
from agri_shock.ingestion.replay import replay
from agri_shock.streaming.contracts import dead_letter_event_id


def _valid_mandi() -> dict[str, object]:
    return {
        "State": "Maharashtra",
        "District": "Nashik",
        "Market": "Lasalgaon",
        "Commodity": "Onion",
        "Arrival_Date": "01/08/2025",
        "Min_Price": 100,
        "Modal_Price": 150,
        "Max_Price": 200,
    }


def test_malformed_producer_record_preserves_raw_provenance_in_dlq() -> None:
    publisher = MemoryPublisher()
    MandiProducer(publisher, RetryPolicy(initial_backoff_seconds=0)).ingest([{"State": "Maharashtra"}])

    topic, _, dead_letter = publisher.messages[0]
    assert topic == "dead-letter-events"
    assert dead_letter.payload["stage"] == "normalize"
    assert dead_letter.payload["reason"] == "missing_arrival_date"
    assert dead_letter.payload["source_topic"] == "mandi-prices"
    assert dead_letter.payload["original_source"] == "ogd_agmarknet"
    assert dead_letter.payload["original_payload"] == {"raw_record": {"State": "Maharashtra"}}
    assert "processing_time" in dead_letter.payload


def test_dead_letter_failure_is_visible_after_bounded_retry() -> None:
    publisher = MemoryPublisher(failures_remaining=2)
    producer = MandiProducer(publisher, RetryPolicy(max_attempts=1, initial_backoff_seconds=0))
    with pytest.raises(RuntimeError, match="dead-letter publication failed"):
        producer.ingest([_valid_mandi()])


def test_dead_letter_identity_is_stable_per_kafka_record_not_just_payload() -> None:
    first = dead_letter_event_id("mandi-prices", 0, 10, "{bad-json")
    assert first == dead_letter_event_id("mandi-prices", 0, 10, "{bad-json")
    assert first != dead_letter_event_id("mandi-prices", 0, 11, "{bad-json")


def test_replaying_identical_fixture_preserves_event_ids_for_downstream_deduplication(tmp_path: Path) -> None:
    fixture = tmp_path / "replay.ndjson"
    fixture.write_text(
        '{"event_id":"replay-1","event_type":"mandi_price","event_time":"2024-07-01T00:00:00Z","ingestion_time":"2024-07-02T00:00:00Z","source":"replayed_historical","schema_version":"1.0","payload":{"state":"Assam"}}\n',
        encoding="utf-8",
    )
    publisher = MemoryPublisher()

    assert replay(fixture, publisher, "mandi-prices", events_per_second=1_000_000) == 1
    assert replay(fixture, publisher, "mandi-prices", events_per_second=1_000_000) == 1
    assert [event.event_id for _, _, event in publisher.messages] == ["replay-1", "replay-1"]
