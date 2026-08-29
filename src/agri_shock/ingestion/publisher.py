"""Kafka publishing boundary with a test-friendly protocol."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from typing import Protocol

from agri_shock.common.events import EventEnvelope


class PublishError(RuntimeError):
    """A transient or permanent broker delivery failure."""


class EventPublisher(Protocol):
    def publish(self, topic: str, key: str, event: EventEnvelope) -> None: ...


@dataclass
class MemoryPublisher:
    """Deterministic publisher for unit/integration-like tests and replay demos."""

    messages: list[tuple[str, str, EventEnvelope]] = field(default_factory=list)
    failures_remaining: int = 0

    def publish(self, topic: str, key: str, event: EventEnvelope) -> None:
        if self.failures_remaining:
            self.failures_remaining -= 1
            raise PublishError("injected publisher failure")
        self.messages.append((topic, key, event))


class KafkaJsonPublisher:
    """Optional runtime adapter; dependency is deliberately imported lazily."""

    def __init__(self, bootstrap_servers: str) -> None:
        try:
            from confluent_kafka import Producer  # type: ignore[import-not-found]
        except ImportError as error:
            raise RuntimeError("Install the kafka extra to use KafkaJsonPublisher") from error
        self._producer = Producer({"bootstrap.servers": bootstrap_servers, "enable.idempotence": True})

    def publish(self, topic: str, key: str, event: EventEnvelope) -> None:
        delivered: list[Exception] = []

        def callback(error: object, _message: object) -> None:
            if error is not None:
                delivered.append(PublishError(str(error)))

        self._producer.produce(topic, key=key.encode(), value=event.to_json().encode(), on_delivery=callback)
        self._producer.flush(10)
        if delivered:
            raise delivered[0]
