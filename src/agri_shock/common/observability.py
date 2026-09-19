"""Small, dependency-free operational metrics and Spark progress contracts."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True, slots=True)
class HealthSummary:
    counts: Mapping[str, int]
    warnings: tuple[str, ...]


class PipelineMetrics:
    def __init__(self, run_id: str) -> None:
        self.run_id = run_id
        self._counts: Counter[str] = Counter()

    def increment(self, metric: str, amount: int = 1) -> None:
        if amount < 0:
            raise ValueError("metrics cannot be decremented")
        self._counts[metric] += amount

    def snapshot(self) -> dict[str, Any]:
        return {"run_id": self.run_id, "counts": dict(sorted(self._counts.items()))}


def summarize_health(counts: Mapping[str, int], max_dlq_rate: float = 0.05) -> HealthSummary:
    if not 0 <= max_dlq_rate <= 1:
        raise ValueError("max_dlq_rate must be in [0, 1]")
    ingested = counts.get("events_ingested", 0)
    dlq = counts.get("dlq_events", 0)
    unresolved = counts.get("unresolved_mappings", 0)
    warnings: list[str] = []
    if ingested and dlq / ingested > max_dlq_rate:
        warnings.append("dlq_rate_exceeds_threshold")
    if unresolved:
        warnings.append("unresolved_geography_present")
    return HealthSummary(dict(counts), tuple(warnings))


def spark_progress_metrics(progress: Mapping[str, Any]) -> dict[str, Any]:
    """Extract only fields Structured Streaming actually reports."""
    event_time = progress.get("eventTime", {})
    return {
        "batch_id": progress.get("batchId"),
        "input_rows": progress.get("numInputRows"),
        "input_rows_per_second": progress.get("inputRowsPerSecond"),
        "processed_rows_per_second": progress.get("processedRowsPerSecond"),
        "batch_duration_ms": progress.get("durationMs", {}).get("triggerExecution"),
        "watermark": event_time.get("watermark") if isinstance(event_time, Mapping) else None,
        "state_operators": progress.get("stateOperators", []),
    }
