"""Reproducible conversion of bounded authoritative historical flood evidence.

This adapter deliberately supports district-reported flood evidence without
inventing a flood polygon or an alert/severity classification.  Its output is
an ordinary AgriShock event envelope, suitable for labelled historical replay.
The immutable source document and its checksum are required inputs.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlparse

from agri_shock.common.events import EventEnvelope, stable_event_id, utc_now
from agri_shock.ingestion.normalizers import NormalizationError, _date, _required


NDEM_SOURCE_HOST = "ndem.nrsc.gov.in"
NDEM_SOURCE_NAME = "nrsc_ndem_rapid_assessment"


@dataclass(frozen=True, slots=True)
class ConversionReport:
    accepted: int
    rejected: tuple[dict[str, Any], ...]


def _source_url(raw: Mapping[str, Any]) -> str:
    url = _required(raw, "source_url")
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != NDEM_SOURCE_HOST:
        raise NormalizationError("unsupported_authoritative_source_url")
    return url


def _sha256(raw: Mapping[str, Any]) -> str:
    value = _required(raw, "artifact_sha256").lower()
    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise NormalizationError("invalid_artifact_sha256")
    return value


def _nonnegative_decimal(raw: Mapping[str, Any], field: str) -> Decimal:
    try:
        value = Decimal(_required(raw, field))
    except (InvalidOperation, ValueError) as error:
        raise NormalizationError(f"invalid_{field.lower()}") from error
    if value < 0:
        raise NormalizationError(f"negative_{field.lower()}")
    return value


def normalize_ndem_district_flood(
    raw: Mapping[str, Any], ingestion_time: datetime | None = None,
) -> EventEnvelope:
    """Normalize one district row from an NRSC/NDEM rapid assessment.

    ``observation_date`` is day-precision source evidence.  Midnight UTC is
    only the canonical representation required by the envelope; the payload
    retains ``event_time_precision=day`` so it cannot be read as a claimed
    observation hour.  ``inundated_area_hectares`` is a reported measurement,
    not an AgriShock severity score.
    """
    if str(raw.get("severity", "")).strip():
        raise NormalizationError("unsupported_severity_field")
    observation_time = _date(_required(raw, "observation_date"), "observation_date")
    window_start = _date(_required(raw, "event_window_start"), "event_window_start")
    window_end = _date(_required(raw, "event_window_end"), "event_window_end")
    if window_start > window_end or observation_time < window_start or observation_time > window_end:
        raise NormalizationError("invalid_event_window")
    source_url = _source_url(raw)
    artifact_sha256 = _sha256(raw)
    state = _required(raw, "state")
    district = _required(raw, "district")
    map_id = _required(raw, "map_id")
    inundated_area = _nonnegative_decimal(raw, "inundated_area_hectares")
    source_key = f"{map_id}|{state}|{district}|{observation_time.date().isoformat()}"
    payload = {
        "source_event_id": f"{map_id}:{state}:{district}",
        "event_start": window_start.isoformat(),
        "event_end": window_end.isoformat(),
        "geometry_json": None,
        "alert_level": None,
        "reported_state": state,
        "reported_district": district,
        "geography_basis": "source_reported_district",
        "event_time_precision": "day",
        "inundated_area_hectares": str(inundated_area),
        "severity_basis": None,
        "source_provider": _required(raw, "source_provider"),
        "source_report_title": _required(raw, "source_report_title"),
        "source_url": source_url,
        "source_map_id": map_id,
        "artifact_sha256": artifact_sha256,
        "source_classification": "replayed_historical",
    }
    return EventEnvelope(
        stable_event_id(NDEM_SOURCE_NAME, source_key, observation_time),
        "flood_event", observation_time, ingestion_time or utc_now(),
        "replayed_historical", "1.1", payload,
    )


def convert_ndem_extract(records: list[Mapping[str, Any]], ingestion_time: datetime | None = None) -> tuple[list[EventEnvelope], ConversionReport]:
    """Convert all supplied rows while preserving explicit rejection reasons."""
    events: list[EventEnvelope] = []
    rejected: list[dict[str, Any]] = []
    for index, record in enumerate(records):
        try:
            events.append(normalize_ndem_district_flood(record, ingestion_time))
        except (NormalizationError, ValueError) as error:
            rejected.append({"row_index": index, "reason": str(error), "raw_record": dict(record)})
    return events, ConversionReport(len(events), tuple(rejected))


def write_conversion(input_path: Path, output_path: Path, manifest_path: Path) -> ConversionReport:
    """Convert a recorded extraction JSON array into replayable NDJSON."""
    records = json.loads(input_path.read_text(encoding="utf-8"))
    if not isinstance(records, list) or not all(isinstance(record, Mapping) for record in records):
        raise ValueError("input must be a JSON array of NRSC/NDEM district records")
    events, report = convert_ndem_extract(records)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(event.to_json() for event in events) + ("\n" if events else ""), encoding="utf-8")
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps({
        "adapter": NDEM_SOURCE_NAME,
        "retrieved_at": utc_now().isoformat(),
        "input_file": str(input_path),
        "input_sha256": sha256(input_path.read_bytes()).hexdigest(),
        "output_file": str(output_path),
        "accepted": report.accepted,
        "rejected": list(report.rejected),
        "replay_classification": "replayed_historical",
    }, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert NRSC/NDEM district flood evidence for replay.")
    parser.add_argument("input", type=Path, help="JSON array extracted from a preserved official artifact")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    report = write_conversion(args.input, args.output, args.manifest)
    print(f"accepted={report.accepted} rejected={len(report.rejected)}")


if __name__ == "__main__":
    main()
