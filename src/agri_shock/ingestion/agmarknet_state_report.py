"""Replayable import of an official AGMARKNET State daily-report CSV.

The report is stateful: market and commodity are context rows. A blank
commodity cell means the preceding commodity; no geography is ever inferred.
"""
from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any, Iterable, Mapping

from agri_shock.common.events import EventEnvelope
from agri_shock.geospatial.case_reference import load_case_market_snapshot, resolve_market_district
from agri_shock.ingestion.normalizers import NormalizationError, normalize_mandi

INPUT_URL = "https://agmarknet.gov.in/marketwisedailystatereportinput"
OUTPUT_URL = "https://agmarknet.gov.in/marketwisedailystatereportoutput"
PROVIDER = "Directorate of Marketing & Inspection (AGMARKNET 2.0)"
SOURCE = "agmarknet_2_state_daily_report"
TITLE = re.compile(r"on\s+(?P<date>\d{2}-[A-Za-z]{3}-\d{4})\s+State/UT\s*:\s*(?P<state>.+?)\s*$", re.I)


@dataclass(frozen=True, slots=True)
class ParsedReport:
    state: str
    arrival_date: str
    rows: tuple[dict[str, Any], ...]


@dataclass(frozen=True, slots=True)
class ImportResult:
    events: tuple[EventEnvelope, ...]
    rejected: tuple[dict[str, Any], ...]
    selected_rows: tuple[dict[str, Any], ...]


def parse_state_daily_report(text: str) -> ParsedReport:
    lines = text.lstrip("\ufeff").splitlines()
    if len(lines) < 3:
        raise ValueError("report_too_short")
    match = TITLE.search(lines[0].strip().strip('"'))
    if not match:
        raise ValueError("unrecognized_report_title")
    try:
        arrival_date = datetime.strptime(match.group("date"), "%d-%b-%Y").strftime("%d/%m/%Y")
    except ValueError as error:
        raise ValueError("invalid_report_date") from error
    market: str | None = None
    commodity: str | None = None
    rows: list[dict[str, Any]] = []
    # The first line is the report title, then a blank line, then the CSV
    # header.  Parse data only after that explicit header.
    for line_number, values in enumerate(csv.reader(lines[3:]), start=4):
        if not values or not any(value.strip() for value in values):
            continue
        first = values[0].strip()
        if first.startswith("Market Name :"):
            market, commodity = first.split(":", 1)[1].strip() or None, None
            continue
        if first.startswith("Commodity Group Name :"):
            continue
        if len(values) != 8:
            rows.append({"_parse_error": "unexpected_column_count", "_line_number": line_number, "_raw_values": values})
            continue
        row_commodity = first or commodity
        if first:
            commodity = first
        rows.append({
            "State": match.group("state").strip(), "Arrival_Date": arrival_date, "Market": market,
            "Commodity": row_commodity, "Arrivals": values[1].strip() or None,
            "Arrival_Unit": values[2].strip() or None, "Variety": values[3].strip() or None,
            "Min_Price": values[4].strip(), "Max_Price": values[5].strip(),
            "Modal_Price": values[6].strip(), "Price_Unit": values[7].strip(),
            "_line_number": line_number, "_raw_values": values,
        })
    return ParsedReport(match.group("state").strip(), arrival_date, tuple(rows))


def import_report(report: ParsedReport, *, reference: tuple[Mapping[str, Any], ...], target_market: str, target_commodity: str, required_price_unit: str, retrieved_at: datetime | None = None) -> ImportResult:
    """Convert one predeclared series; choose by identity/unit, never prices."""
    selected = tuple(row for row in report.rows if row.get("Market") == target_market and row.get("Commodity") == target_commodity)
    events: list[EventEnvelope] = []
    rejected: list[dict[str, Any]] = []
    now = retrieved_at or datetime.now(timezone.utc)
    for row in selected:
        if "_parse_error" in row:
            rejected.append({"reason": row["_parse_error"], "raw_record": row})
        elif row.get("Price_Unit") != required_price_unit:
            rejected.append({"reason": "incompatible_price_unit", "raw_record": row})
        else:
            resolution = resolve_market_district(str(row["State"]), str(row["Market"]), reference)
            if resolution.status != "resolved" or resolution.record is None:
                rejected.append({"reason": resolution.reason or "unresolved_market_geography", "raw_record": row})
                continue
            canonical = dict(row)
            canonical["District"] = resolution.record["source_district"]
            try:
                events.append(normalize_mandi(canonical, now, source=SOURCE))
            except (NormalizationError, ValueError) as error:
                rejected.append({"reason": str(error), "raw_record": row})
    return ImportResult(tuple(events), tuple(rejected), selected)


def coverage_by_variety(events: Iterable[EventEnvelope]) -> dict[str, dict[str, Any]]:
    values: dict[str, list[str]] = {}
    for event in events:
        values.setdefault(str(event.payload.get("variety") or "<unspecified>"), []).append(event.event_time.date().isoformat())
    return {variety: {"observation_count": len(dates), "unique_dates": len(set(dates)), "earliest_date": min(dates), "latest_date": max(dates)} for variety, dates in sorted(values.items())}


def write_import_artifacts(result: ImportResult, report_file: Path, output_dir: Path, *, target_market: str, target_commodity: str, required_price_unit: str, retrieved_at: datetime) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    digest = sha256(report_file.read_bytes()).hexdigest()
    stem = f"agmarknet-state-daily-{digest[:16]}"
    replay, rejected, manifest = (output_dir / f"{stem}.replayed.ndjson", output_dir / f"{stem}.rejected.ndjson", output_dir / f"{stem}.manifest.json")
    replay.write_text("\n".join(event.to_json() for event in result.events) + ("\n" if result.events else ""), encoding="utf-8")
    rejected.write_text("\n".join(json.dumps(row, sort_keys=True, default=str) for row in result.rejected) + ("\n" if result.rejected else ""), encoding="utf-8")
    manifest.write_text(json.dumps({
        "classification": "replayed_historical", "provider": PROVIDER, "source": SOURCE, "input_url": INPUT_URL, "output_url": OUTPUT_URL, "retrieved_at": retrieved_at.isoformat(), "raw_report_path": str(report_file), "raw_report_sha256": digest,
        "request_filters": {"state": result.selected_rows[0]["State"] if result.selected_rows else None, "target_market": target_market, "target_commodity": target_commodity, "price_unit": required_price_unit}, "accepted_rows": len(result.events), "rejected_rows": len(result.rejected), "variety_coverage": coverage_by_variety(result.events),
        "raw_source_fields": ["Market Name context", "Commodity Group context", "Commodity", "Arrivals", "Unit of Arrivals", "Variety", "Minimum Prices", "Maximum Prices", "Modal Prices", "Unit of Price"],
    }, indent=2, sort_keys=True), encoding="utf-8")
    return {"replay_file": str(replay), "rejected_file": str(rejected), "manifest": str(manifest)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Import a manually exported official AGMARKNET State daily report")
    parser.add_argument("--report-file", required=True, type=Path)
    parser.add_argument("--market-reference", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--target-market", required=True)
    parser.add_argument("--target-commodity", required=True)
    parser.add_argument("--price-unit", default="Rs./Quintal")
    args = parser.parse_args()
    report = parse_state_daily_report(args.report_file.read_text(encoding="utf-8"))
    result = import_report(report, reference=load_case_market_snapshot(args.market_reference), target_market=args.target_market, target_commodity=args.target_commodity, required_price_unit=args.price_unit)
    paths = write_import_artifacts(result, args.report_file, args.output_dir, target_market=args.target_market, target_commodity=args.target_commodity, required_price_unit=args.price_unit, retrieved_at=datetime.now(timezone.utc))
    print(json.dumps({**paths, "accepted_rows": len(result.events), "rejected_rows": len(result.rejected), "variety_coverage": coverage_by_variety(result.events)}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
