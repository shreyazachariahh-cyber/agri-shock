"""OGD/AGMARKNET ingestion adapter; live API access requires a project key."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any, Mapping

from agri_shock.common.events import EventEnvelope
from agri_shock.ingestion.base import ProducerBase, ProducerReport
from agri_shock.ingestion.normalizers import normalize_mandi
from agri_shock.ingestion.http import fetch_json


class MandiProducer(ProducerBase):
    topic = "mandi-prices"

    def ingest(self, records: Iterable[Mapping[str, Any]]) -> ProducerReport:
        events: list[EventEnvelope] = []
        rejected = 0
        for record in records:
            try:
                events.append(normalize_mandi(record))
            except Exception as error:
                self.reject_raw("ogd_agmarknet", "mandi_price", record, str(error))
                rejected += 1
        report = self.publish_events(events, lambda event: "|".join(str(event.payload[field]) for field in ("state", "district", "market")))
        return ProducerReport(report.published, report.rejected + rejected)

    def fetch_and_ingest(self, url: str) -> ProducerReport:
        payload = fetch_json(url)
        if not isinstance(payload, Mapping) or not isinstance(payload.get("records"), list):
            raise ValueError("OGD response lacks records array")
        return self.ingest(payload["records"])
