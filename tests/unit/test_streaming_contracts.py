import pytest
from agri_shock.streaming.contracts import EventTimePolicy, dead_letter_event_id

def test_watermark_requires_explicit_positive_duration() -> None:
    assert EventTimePolicy(72).spark_duration == "72 hours"
    with pytest.raises(ValueError):
        EventTimePolicy(0)


def test_dead_letter_identity_rejects_invalid_kafka_coordinates() -> None:
    with pytest.raises(ValueError, match="Kafka topic"):
        dead_letter_event_id("", 0, 0, "{}")
