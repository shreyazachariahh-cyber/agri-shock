from agri_shock.ingestion.publisher import MemoryPublisher
from agri_shock.ingestion.replay import parse_event


def test_replay_requires_labelled_source() -> None:
    line = '{"event_id":"x","event_type":"mandi_price","event_time":"2025-01-01T00:00:00Z","ingestion_time":"2025-01-02T00:00:00Z","source":"ogd_agmarknet","schema_version":"1.0","payload":{}}'
    try:
        parse_event(line)
    except ValueError as error:
        assert "explicitly labelled" in str(error)
    else:
        raise AssertionError("unlabelled replay accepted")
