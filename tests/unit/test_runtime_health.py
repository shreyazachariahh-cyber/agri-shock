from agri_shock.runtime.health import TABLES
from agri_shock.streaming.contracts import DLQ_DELTA_RELATIVE_PATH


def test_health_counts_the_durable_delta_dlq_location() -> None:
    assert TABLES["dlq_events"] == DLQ_DELTA_RELATIVE_PATH
