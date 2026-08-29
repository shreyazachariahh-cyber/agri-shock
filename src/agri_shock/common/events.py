"""Source-neutral event contracts used at ingestion boundaries."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Any, Mapping
from uuid import UUID


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def require_aware(value: datetime, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    return value.astimezone(timezone.utc)


def stable_event_id(source: str, source_key: str, event_time: datetime) -> str:
    """Create a deterministic, opaque identifier for retry-safe ingestion."""
    material = f"{source}|{source_key}|{require_aware(event_time, 'event_time').isoformat()}"
    return sha256(material.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class EventEnvelope:
    event_id: str
    event_type: str
    event_time: datetime
    ingestion_time: datetime
    source: str
    schema_version: str
    payload: Mapping[str, Any]

    def __post_init__(self) -> None:
        if not self.event_id or not self.event_type or not self.source:
            raise ValueError("event_id, event_type, and source are required")
        if not self.schema_version:
            raise ValueError("schema_version is required")
        require_aware(self.event_time, "event_time")
        require_aware(self.ingestion_time, "ingestion_time")

    def to_json(self) -> str:
        data = asdict(self)
        data["event_time"] = require_aware(self.event_time, "event_time").isoformat()
        data["ingestion_time"] = require_aware(self.ingestion_time, "ingestion_time").isoformat()
        return json.dumps(data, sort_keys=True, default=str)
