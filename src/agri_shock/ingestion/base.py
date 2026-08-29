"""Shared producer mechanics: bounded retries, validation, and DLQ routing."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import logging
import time
from typing import Callable, Iterable

from agri_shock.common.events import EventEnvelope
from agri_shock.ingestion.publisher import EventPublisher

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    max_attempts: int = 3
    initial_backoff_seconds: float = 1.0

    def __post_init__(self) -> None:
        if self.max_attempts < 1 or self.initial_backoff_seconds < 0:
            raise ValueError("retry policy values are invalid")


@dataclass(frozen=True, slots=True)
class ProducerReport:
    published: int = 0
    rejected: int = 0


class ProducerBase:
    topic: str

    def __init__(self, publisher: EventPublisher, retry_policy: RetryPolicy, dlq_topic: str = "dead-letter-events", sleep: Callable[[float], None] = time.sleep) -> None:
        self.publisher = publisher
        self.retry_policy = retry_policy
        self.dlq_topic = dlq_topic
        self.sleep = sleep

    def publish_events(self, events: Iterable[EventEnvelope], partition_key: Callable[[EventEnvelope], str]) -> ProducerReport:
        published = rejected = 0
        for event in events:
            try:
                self._publish_with_retry(self.topic, partition_key(event), event)
                published += 1
            except Exception as error:
                self._route_dlq(event, stage="publish", reason=str(error))
                rejected += 1
        return ProducerReport(published, rejected)

    def _publish_with_retry(self, topic: str, key: str, event: EventEnvelope) -> None:
        for attempt in range(1, self.retry_policy.max_attempts + 1):
            try:
                self.publisher.publish(topic, key, event)
                return
            except Exception:
                if attempt == self.retry_policy.max_attempts:
                    raise
                self.sleep(self.retry_policy.initial_backoff_seconds * 2 ** (attempt - 1))

    def _route_dlq(self, event: EventEnvelope, stage: str, reason: str) -> None:
        dlq = EventEnvelope(
            event_id=f"dlq:{event.event_id}:{stage}", event_type="dead_letter_event",
            event_time=event.event_time, ingestion_time=datetime.now(timezone.utc),
            source="agrishock", schema_version="1.0",
            payload={"reason": reason, "stage": stage, "original_event_id": event.event_id, "original_event_type": event.event_type},
        )
        try:
            self.publisher.publish(self.dlq_topic, event.event_id, dlq)
        except Exception:
            LOGGER.exception("dead-letter publication failed", extra={"event_id": event.event_id, "stage": stage})

    def reject_raw(self, source: str, event_type: str, raw_record: object, reason: str) -> None:
        """Preserve malformed input in the DLQ instead of silently discarding it."""
        encoded = json.dumps(raw_record, sort_keys=True, default=str)
        rejected = EventEnvelope(
            event_id=f"rejected:{sha256((source + encoded).encode()).hexdigest()}",
            event_type=event_type, event_time=datetime.now(timezone.utc), ingestion_time=datetime.now(timezone.utc),
            source=source, schema_version="1.0", payload={"raw_record": raw_record},
        )
        self._route_dlq(rejected, stage="normalize", reason=reason)
