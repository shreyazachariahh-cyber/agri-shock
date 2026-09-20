"""Bounded OGD/AGMARKNET acquisition and coverage audit for historical replay.

This module never claims that the current-daily OGD resource is a complete
historical archive. It records the exact bounded request and observed coverage
so suitability is established before a case study is selected.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import urlencode

from agri_shock.common.events import EventEnvelope
from agri_shock.ingestion.http import fetch_json
from agri_shock.ingestion.normalizers import NormalizationError, normalize_mandi

OGD_RESOURCE_ID = "9ef84268-d588-465a-a308-a864a43d0070"
OGD_CATALOG_URL = "https://sandbox.data.gov.in/catalog/current-daily-price-various-commodities-various-markets-mandi"
OGD_RESOURCE_URL = "https://api.data.gov.in/resource/"
PROVIDER = "Ministry of Agriculture and Farmers Welfare / Directorate of Marketing & Inspection (AGMARKNET)"
DOCUMENTED_PRICE_UNIT = "INR/quintal"
CRITICAL_FIELDS = ("State", "District", "Market", "Commodity", "Variety", "Arrival_Date", "Min_Price", "Modal_Price", "Max_Price")


@dataclass(frozen=True, slots=True)
class ConversionResult:
    events: tuple[EventEnvelope, ...]
    rejected: tuple[dict[str, Any], ...]
    raw_fields: tuple[str, ...]


def build_ogd_url(api_key: str, *, resource_id: str = OGD_RESOURCE_ID, limit: int = 10, offset: int = 0) -> str:
    if not api_key.strip():
        raise ValueError("DATA_GOV_IN_API_KEY is required")
    if not 1 <= limit <= 100:
        raise ValueError("limit must be between 1 and 100 for bounded discovery")
    if offset < 0:
        raise ValueError("offset must be non-negative")
    return f"{OGD_RESOURCE_URL}{resource_id}?{urlencode({'api-key': api_key, 'format': 'json', 'limit': limit, 'offset': offset})}"


def safe_request_parameters(*, resource_id: str, limit: int, offset: int) -> dict[str, object]:
    return {"resource_id": resource_id, "format": "json", "limit": limit, "offset": offset}


def convert_records(records: Sequence[Mapping[str, Any]], retrieved_at: datetime | None = None) -> ConversionResult:
    events: list[EventEnvelope] = []
    rejected: list[dict[str, Any]] = []
    fields = sorted({str(key) for record in records for key in record})
    for record in records:
        try:
            normalized = normalize_mandi(record, documented_price_unit=DOCUMENTED_PRICE_UNIT)
            events.append(EventEnvelope(normalized.event_id, normalized.event_type, normalized.event_time, retrieved_at or datetime.now(timezone.utc), "replayed_historical", normalized.schema_version, normalized.payload))
        except (NormalizationError, ValueError) as error:
            rejected.append({"reason": str(error), "raw_record": dict(record)})
    return ConversionResult(tuple(events), tuple(rejected), tuple(fields))


def write_artifact(output_dir: Path, payload: Mapping[str, Any], result: ConversionResult, *, resource_id: str, limit: int, offset: int, retrieved_at: datetime) -> tuple[Path, Path]:
    if not isinstance(payload.get("records"), list):
        raise ValueError("OGD response lacks records array")
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = f"ogd-agmarknet-{resource_id}-{retrieved_at.strftime('%Y%m%dT%H%M%SZ')}"
    raw_path, replay_path = output_dir / f"{stem}.raw.json", output_dir / f"{stem}.replayed.ndjson"
    raw_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    replay_path.write_text("\n".join(event.to_json() for event in result.events) + ("\n" if result.events else ""), encoding="utf-8")
    manifest = {
        "classification": "replayed_historical", "provider": PROVIDER,
        "catalog_url": OGD_CATALOG_URL, "resource_url": f"{OGD_RESOURCE_URL}{resource_id}",
        "retrieved_at": retrieved_at.isoformat(), "request_parameters": safe_request_parameters(resource_id=resource_id, limit=limit, offset=offset),
        "raw_source_fields": list(result.raw_fields), "accepted_rows": len(result.events), "rejected_rows": len(result.rejected),
        "documented_price_unit": DOCUMENTED_PRICE_UNIT,
        "price_unit_note": "OGD catalogue describes AGMARKNET prices as rupees per quintal; used only when a row has no Price_Unit field.",
        "rejections": list(result.rejected), "raw_file": raw_path.name, "replay_file": replay_path.name,
    }
    (output_dir / f"{stem}.manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True, default=str), encoding="utf-8")
    return raw_path, replay_path


def coverage_report(records: Sequence[Mapping[str, Any]]) -> dict[str, object]:
    result = convert_records(records, datetime(2000, 1, 1, tzinfo=timezone.utc))
    dates = sorted(event.event_time.date().isoformat() for event in result.events)
    def values(field: str) -> list[str]: return sorted({str(record.get(field, "")).strip() for record in records if str(record.get(field, "")).strip()})
    total = len(records)
    return {"row_count": total, "accepted_rows": len(result.events), "rejected_rows": len(result.rejected), "earliest_date": dates[0] if dates else None, "latest_date": dates[-1] if dates else None, "states": values("State"), "districts": values("District"), "markets": values("Market"), "commodities": values("Commodity"), "varieties": values("Variety"), "missing_rates": {field: (sum(not str(row.get(field, "")).strip() for row in records) / total if total else None) for field in CRITICAL_FIELDS}}


def main() -> None:
    parser = argparse.ArgumentParser(description="Acquire or audit a bounded official OGD/AGMARKNET mandi sample")
    sub = parser.add_subparsers(dest="command", required=True)
    fetch = sub.add_parser("fetch"); fetch.add_argument("--output-dir", type=Path, required=True); fetch.add_argument("--limit", type=int, default=10); fetch.add_argument("--offset", type=int, default=0); fetch.add_argument("--resource-id", default=OGD_RESOURCE_ID)
    audit = sub.add_parser("audit"); audit.add_argument("--raw-file", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "fetch":
        key = os.getenv("DATA_GOV_IN_API_KEY", "")
        url = build_ogd_url(key, resource_id=args.resource_id, limit=args.limit, offset=args.offset)
        payload = fetch_json(url)
        if not isinstance(payload, Mapping) or not isinstance(payload.get("records"), list): raise ValueError("OGD response lacks records array")
        now = datetime.now(timezone.utc); result = convert_records(payload["records"], now)
        raw, replay = write_artifact(args.output_dir, payload, result, resource_id=args.resource_id, limit=args.limit, offset=args.offset, retrieved_at=now)
        print(json.dumps({"raw_file": str(raw), "replay_file": str(replay), **coverage_report(payload["records"])}, indent=2))
    else:
        payload = json.loads(args.raw_file.read_text(encoding="utf-8"))
        if not isinstance(payload, Mapping) or not isinstance(payload.get("records"), list): raise ValueError("OGD response lacks records array")
        print(json.dumps(coverage_report(payload["records"]), indent=2))


if __name__ == "__main__": main()
