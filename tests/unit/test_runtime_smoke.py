from pathlib import Path

import pytest

from agri_shock.ingestion.publisher import MemoryPublisher
from agri_shock.runtime.smoke import (
    SmokePaths,
    expected_signal_id,
    publish_synthetic_events,
    synthetic_events,
    verify_delta_layout,
    verify_elasticsearch_signal,
)


def test_synthetic_smoke_events_cover_all_ingestion_topics_and_publish() -> None:
    topics = {topic for topic, _ in synthetic_events()}
    assert topics == {"mandi-prices", "weather-events", "flood-events"}
    publisher = MemoryPublisher()
    assert publish_synthetic_events("unused", publisher) == 3
    assert len(publisher.messages) == 3


def test_expected_signal_id_is_deterministic() -> None:
    assert expected_signal_id() == expected_signal_id()


def test_delta_layout_requires_all_transaction_logs(tmp_path: Path) -> None:
    paths = SmokePaths(tmp_path)
    with pytest.raises(RuntimeError, match="missing Delta table paths"):
        verify_delta_layout(paths)
    for table in paths.required_tables:
        (table / "_delta_log").mkdir(parents=True)
    verify_delta_layout(paths)


def test_elasticsearch_verification_requires_the_expected_id() -> None:
    signal_id = expected_signal_id()
    verify_elasticsearch_signal("http://example.test", signal_id, lambda _: f'{{"_id":"{signal_id}"}}'.encode())
    with pytest.raises(RuntimeError, match="did not return"):
        verify_elasticsearch_signal("http://example.test", signal_id, lambda _: b'{"found":false}')
