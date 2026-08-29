from datetime import datetime, timezone

import pytest

from agri_shock.common.events import EventEnvelope, stable_event_id


def test_stable_event_id_is_deterministic() -> None:
    timestamp = datetime(2025, 8, 1, tzinfo=timezone.utc)
    assert stable_event_id("imd", "164", timestamp) == stable_event_id("imd", "164", timestamp)


def test_envelope_rejects_naive_event_time() -> None:
    with pytest.raises(ValueError, match="event_time"):
        EventEnvelope("id", "weather_observation", datetime(2025, 1, 1), datetime.now(timezone.utc), "imd", "1.0", {})
