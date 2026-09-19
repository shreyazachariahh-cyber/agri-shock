from agri_shock.common.observability import PipelineMetrics, spark_progress_metrics, summarize_health
from agri_shock.runtime.benchmark import benchmark_publish
from agri_shock.ingestion.publisher import MemoryPublisher


def test_metrics_snapshot_and_health_warnings_are_measurable() -> None:
    metrics = PipelineMetrics("run-1")
    metrics.increment("events_ingested", 10)
    metrics.increment("dlq_events", 1)
    metrics.increment("unresolved_mappings", 1)
    summary = summarize_health(metrics.snapshot()["counts"], max_dlq_rate=0.05)
    assert summary.warnings == ("dlq_rate_exceeds_threshold", "unresolved_geography_present")


def test_spark_progress_extracts_only_reported_fields() -> None:
    progress = spark_progress_metrics({"batchId": 7, "numInputRows": 3, "durationMs": {"triggerExecution": 25}, "eventTime": {"watermark": "2024-01-01T00:00:00.000Z"}, "stateOperators": [{"numRowsTotal": 2}]})
    assert progress["batch_id"] == 7
    assert progress["watermark"] == "2024-01-01T00:00:00.000Z"


def test_benchmark_reports_dispatch_without_claiming_end_to_end_throughput() -> None:
    result = benchmark_publish(MemoryPublisher(), events=5, duplicate_every=2)
    assert result.events == 5
    assert result.duplicate_events == 2
    assert result.throughput_events_per_second >= 0
    assert result.measurement == "publisher_dispatch_only"
