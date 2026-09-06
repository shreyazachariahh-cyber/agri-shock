"""Replay labelled historical NDJSON while preserving original event time."""

from __future__ import annotations

import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import time

from agri_shock.common.events import EventEnvelope
from agri_shock.ingestion.publisher import EventPublisher, KafkaJsonPublisher, MemoryPublisher


def parse_event(line: str) -> EventEnvelope:
    raw = json.loads(line)
    if raw.get("source") not in {"replayed_historical", "synthetic_failure_injection"}:
        raise ValueError("replay input must be explicitly labelled")
    return EventEnvelope(
        event_id=raw["event_id"], event_type=raw["event_type"],
        event_time=datetime.fromisoformat(raw["event_time"].replace("Z", "+00:00")),
        ingestion_time=datetime.fromisoformat(raw["ingestion_time"].replace("Z", "+00:00")),
        source=raw["source"], schema_version=raw["schema_version"], payload=raw["payload"],
    )


def replay(path: Path, publisher: EventPublisher, topic: str, events_per_second: float = 1.0) -> int:
    if events_per_second <= 0:
        raise ValueError("events_per_second must be positive")
    count = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        event = parse_event(line)
        publisher.publish(topic, event.event_id, event)
        count += 1
        time.sleep(1 / events_per_second)
    return count


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    parser.add_argument("--topic", default="mandi-prices")
    parser.add_argument("--events-per-second", type=float, default=1.0)
    parser.add_argument("--sink", choices=("memory", "kafka"), default="memory")
    args = parser.parse_args()
    publisher: EventPublisher = MemoryPublisher() if args.sink == "memory" else KafkaJsonPublisher(os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"))
    count = replay(args.path, publisher, args.topic, args.events_per_second)
    print(f"Replayed {count} labelled events to {args.sink} sink.")


if __name__ == "__main__":
    main()
