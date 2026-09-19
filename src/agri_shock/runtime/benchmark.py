"""Reproducible local publisher-dispatch benchmark; not an end-to-end claim."""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from time import perf_counter
from typing import Any

from agri_shock.runtime.smoke import synthetic_events


@dataclass(frozen=True, slots=True)
class BenchmarkResult:
    events: int
    elapsed_seconds: float
    throughput_events_per_second: float
    duplicate_events: int
    measurement: str = "publisher_dispatch_only"


def benchmark_publish(publisher: Any, events: int, duplicate_every: int = 0) -> BenchmarkResult:
    if events <= 0 or duplicate_every < 0:
        raise ValueError("events must be positive and duplicate_every non-negative")
    templates = synthetic_events()
    started = perf_counter()
    duplicates = 0
    for index in range(events):
        topic, event = templates[index % len(templates)]
        publisher.publish(topic, event.event_id, event)
        if duplicate_every and (index + 1) % duplicate_every == 0:
            publisher.publish(topic, event.event_id, event)
            duplicates += 1
    elapsed = perf_counter() - started
    return BenchmarkResult(events, elapsed, events / elapsed if elapsed else 0.0, duplicates)


def main() -> None:
    from agri_shock.ingestion.publisher import KafkaJsonPublisher, MemoryPublisher

    parser = argparse.ArgumentParser(description="Measure AgriShock publisher dispatch only")
    parser.add_argument("--events", type=int, default=100)
    parser.add_argument("--duplicate-every", type=int, default=0)
    parser.add_argument("--sink", choices=("memory", "kafka"), default="memory")
    parser.add_argument("--bootstrap", default="localhost:9092")
    args = parser.parse_args()
    publisher = MemoryPublisher() if args.sink == "memory" else KafkaJsonPublisher(args.bootstrap)
    print(asdict(benchmark_publish(publisher, args.events, args.duplicate_every)))


if __name__ == "__main__":
    main()
