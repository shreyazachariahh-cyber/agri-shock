"""IMD district rainfall adapter; access status is documented in data-sources.md."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any, Mapping

from agri_shock.common.events import EventEnvelope
from agri_shock.ingestion.base import ProducerBase, ProducerReport
from agri_shock.ingestion.normalizers import normalize_weather


class WeatherProducer(ProducerBase):
    topic = "weather-events"

    def ingest(self, records: Iterable[Mapping[str, Any]]) -> ProducerReport:
        events: list[EventEnvelope] = []
        rejected = 0
        for record in records:
            try:
                events.append(normalize_weather(record))
            except Exception as error:
                self.reject_raw("imd", "weather_observation", record, str(error))
                rejected += 1
        report = self.publish_events(events, lambda event: "|".join(str(event.payload.get(field) or "unknown") for field in ("state", "district")))
        return ProducerReport(report.published, report.rejected + rejected)
