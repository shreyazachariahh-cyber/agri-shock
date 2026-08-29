from agri_shock.ingestion.base import RetryPolicy
from agri_shock.ingestion.mandi_producer import MandiProducer
from agri_shock.ingestion.publisher import MemoryPublisher


def valid_record() -> dict[str, object]:
    return {"State": "Maharashtra", "District": "Nashik", "Market": "Lasalgaon", "Commodity": "Onion", "Variety": "Other", "Arrival_Date": "01/08/2025", "Min_Price": 100, "Modal_Price": 150, "Max_Price": 200}


def test_mandi_producer_routes_bad_record_to_dlq() -> None:
    publisher = MemoryPublisher()
    report = MandiProducer(publisher, RetryPolicy(initial_backoff_seconds=0)).ingest([valid_record(), {"State": "Maharashtra"}])
    assert (report.published, report.rejected) == (1, 1)
    assert [message[0] for message in publisher.messages] == ["dead-letter-events", "mandi-prices"]


def test_publish_retries() -> None:
    publisher = MemoryPublisher(failures_remaining=1)
    report = MandiProducer(publisher, RetryPolicy(max_attempts=2, initial_backoff_seconds=0)).ingest([valid_record()])
    assert report.published == 1
