"""GDACS GeoJSON adapter. District mapping is intentionally deferred to Phase 4."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any, Mapping

from agri_shock.common.events import EventEnvelope
from agri_shock.ingestion.base import ProducerBase, ProducerReport
from agri_shock.ingestion.normalizers import normalize_flood


class FloodProducer(ProducerBase):
    topic = "flood-events"

    def ingest(self, features: Iterable[Mapping[str, Any]]) -> ProducerReport:
        events: list[EventEnvelope] = []
        rejected = 0
        for feature in features:
            try:
                events.append(normalize_flood(feature))
            except Exception as error:
                self.reject_raw("gdacs", "flood_event", feature, str(error))
                rejected += 1
        report = self.publish_events(events, lambda event: str(event.payload["source_event_id"]))
        return ProducerReport(report.published, report.rejected + rejected)
