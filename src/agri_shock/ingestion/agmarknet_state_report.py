"""Replayable import of an official AGMARKNET State daily-report CSV.

The report is stateful: market and commodity are context rows. A blank
commodity cell means the preceding commodity; no geography is ever inferred.
"""
from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import date, datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
import shutil
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


def audit_batch(
    report_files: Iterable[Path], *, reference: tuple[Mapping[str, Any], ...],
    target_market: str, target_commodity: str, required_price_unit: str,
    pre_event_end: date, known_no_data_dates: Iterable[date] = (),
) -> dict[str, Any]:
    """Audit a predeclared report batch without inspecting price outcomes.

    Raw-file hashes are used only to prevent an identical downloaded report
    from inflating coverage.  A report with no target row is retained as a
    target-series availability gap; it is not a fabricated zero observation.
    """
    seen_hashes: set[str] = set()
    imported: list[tuple[Path, ParsedReport, ImportResult]] = []
    duplicate_files: list[str] = []
    for path in sorted(report_files):
        digest = sha256(path.read_bytes()).hexdigest()
        if digest in seen_hashes:
            duplicate_files.append(str(path))
            continue
        seen_hashes.add(digest)
        report = parse_state_daily_report(path.read_text(encoding="utf-8"))
        imported.append((path, report, import_report(report, reference=reference, target_market=target_market, target_commodity=target_commodity, required_price_unit=required_price_unit)))
    events = tuple(event for _, _, result in imported for event in result.events)
    coverage = sorted(
        [{"market": event.payload["market"], "commodity": event.payload["commodity"], "variety": event.payload["variety"], "price_unit": event.payload["price_unit"], "observation_date": event.event_time.date().isoformat()} for event in events],
        key=lambda row: (str(row["observation_date"]), str(row["variety"])),
    )
    pre_events = tuple(event for event in events if event.event_time.date() < pre_event_end)
    return {
        "target": {"market": target_market, "commodity": target_commodity, "price_unit": required_price_unit},
        "pre_event_end_exclusive": pre_event_end.isoformat(),
        "represented_source_dates": [report.arrival_date for _, report, _ in imported],
        "known_no_data_dates": sorted(item.isoformat() for item in known_no_data_dates),
        "reports_without_target_rows": [report.arrival_date for _, report, result in imported if not result.selected_rows],
        "duplicate_raw_files_excluded": duplicate_files,
        "total_target_rows": sum(len(result.selected_rows) for _, _, result in imported),
        "accepted_rows": len(events),
        "rejected_rows": sum(len(result.rejected) for _, _, result in imported),
        "coverage": coverage,
        "coverage_by_variety": coverage_by_variety(events),
        "pre_event_coverage_by_variety": coverage_by_variety(pre_events),
    }


def write_batch_import_artifacts(
    report_files: Iterable[Path], output_dir: Path, *, reference: tuple[Mapping[str, Any], ...],
    target_market: str, target_commodity: str, required_price_unit: str,
    retrieved_at: datetime,
) -> tuple[dict[str, str], ...]:
    """Materialize a replay/rejection manifest for every distinct raw report."""
    seen_hashes: set[str] = set()
    artifacts: list[dict[str, str]] = []
    for path in sorted(report_files):
        digest = sha256(path.read_bytes()).hexdigest()
        if digest in seen_hashes:
            continue
        seen_hashes.add(digest)
        report = parse_state_daily_report(path.read_text(encoding="utf-8"))
        result = import_report(report, reference=reference, target_market=target_market, target_commodity=target_commodity, required_price_unit=required_price_unit, retrieved_at=retrieved_at)
        artifacts.append(write_import_artifacts(result, path, output_dir, target_market=target_market, target_commodity=target_commodity, required_price_unit=required_price_unit, retrieved_at=retrieved_at))
    return tuple(artifacts)


def stage_downloaded_reports(
    incoming_dir: Path, raw_dir: Path, *, state: str, window_start: date,
    window_end: date,
) -> dict[str, Any]:
    """Discover unrenamed official CSVs and stage only one fixed report window.

    The report's internal title is authoritative for its state and date. Files
    outside the predeclared window are reported but not copied. An identical
    hash is a duplicate; conflicting payloads for one report date are withheld
    rather than arbitrarily choosing one.
    """
    if window_end < window_start:
        raise ValueError("window_end_before_window_start")
    if not incoming_dir.is_dir():
        raise ValueError("incoming_dir_not_found")
    raw_dir.mkdir(parents=True, exist_ok=True)
    accepted: dict[date, tuple[Path, str, ParsedReport]] = {}
    ignored: list[dict[str, str]] = []
    duplicates: list[dict[str, str]] = []
    conflicts: list[dict[str, str]] = []
    for path in sorted(incoming_dir.glob("*.csv")):
        try:
            report = parse_state_daily_report(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, ValueError) as error:
            ignored.append({"file": str(path), "reason": str(error)})
            continue
        report_date = datetime.strptime(report.arrival_date, "%d/%m/%Y").date()
        if report.state.strip().casefold() != state.strip().casefold():
            ignored.append({"file": str(path), "reason": "different_state"})
            continue
        if not window_start <= report_date <= window_end:
            ignored.append({"file": str(path), "reason": "outside_predeclared_window"})
            continue
        digest = sha256(path.read_bytes()).hexdigest()
        previous = accepted.get(report_date)
        if previous is not None:
            if previous[1] == digest:
                duplicates.append({"file": str(path), "duplicate_of": str(previous[0]), "sha256": digest})
            else:
                conflicts.append({"file": str(path), "conflicts_with": str(previous[0]), "report_date": report_date.isoformat()})
            continue
        accepted[report_date] = (path, digest, report)
    staged: list[dict[str, str]] = []
    for report_date, (path, digest, _) in sorted(accepted.items()):
        destination = raw_dir / f"agmarknet-{state.lower().replace(' ', '-')}-{report_date.isoformat()}-{digest[:16]}.csv"
        if not destination.exists():
            shutil.copy2(path, destination)
        staged.append({"source_file": str(path), "raw_file": str(destination), "report_date": report_date.isoformat(), "sha256": digest})
    missing_dates = [date.fromordinal(item).isoformat() for item in range(window_start.toordinal(), window_end.toordinal() + 1) if date.fromordinal(item) not in accepted]
    return {"state": state, "window_start": window_start.isoformat(), "window_end": window_end.isoformat(), "staged_reports": staged, "missing_report_dates": missing_dates, "duplicate_files": duplicates, "conflicting_report_dates": conflicts, "ignored_files": ignored}


def write_import_artifacts(result: ImportResult, report_file: Path, output_dir: Path, *, target_market: str, target_commodity: str, required_price_unit: str, retrieved_at: datetime) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    digest = sha256(report_file.read_bytes()).hexdigest()
    stem = f"agmarknet-state-daily-{digest[:16]}"
    replay, rejected, manifest = (output_dir / f"{stem}.replayed.ndjson", output_dir / f"{stem}.rejected.ndjson", output_dir / f"{stem}.manifest.json")
    # The normalized event ID retains the provider name in its deterministic
    # lineage.  The *delivery mode* is different: this file is a historical
    # replay artifact and must pass the replay gate rather than masquerading as
    # a live provider event.  Keep that distinction in the envelope source.
    replay_events = tuple(EventEnvelope(
        event.event_id, event.event_type, event.event_time, event.ingestion_time,
        "replayed_historical", event.schema_version, event.payload,
    ) for event in result.events)
    replay.write_text("\n".join(event.to_json() for event in replay_events) + ("\n" if replay_events else ""), encoding="utf-8")
    rejected.write_text("\n".join(json.dumps(row, sort_keys=True, default=str) for row in result.rejected) + ("\n" if result.rejected else ""), encoding="utf-8")
    manifest.write_text(json.dumps({
        "classification": "replayed_historical", "provider": PROVIDER, "source": SOURCE, "input_url": INPUT_URL, "output_url": OUTPUT_URL, "retrieved_at": retrieved_at.isoformat(), "raw_report_path": str(report_file), "raw_report_sha256": digest,
        "request_filters": {"state": result.selected_rows[0]["State"] if result.selected_rows else None, "target_market": target_market, "target_commodity": target_commodity, "price_unit": required_price_unit}, "accepted_rows": len(result.events), "rejected_rows": len(result.rejected), "variety_coverage": coverage_by_variety(result.events),
        "raw_source_fields": ["Market Name context", "Commodity Group context", "Commodity", "Arrivals", "Unit of Arrivals", "Variety", "Minimum Prices", "Maximum Prices", "Modal Prices", "Unit of Price"],
    }, indent=2, sort_keys=True), encoding="utf-8")
    return {"replay_file": str(replay), "rejected_file": str(rejected), "manifest": str(manifest)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Import a manually exported official AGMARKNET State daily report")
    parser.add_argument("--report-file", type=Path)
    parser.add_argument("--report-glob")
    parser.add_argument("--incoming-dir", type=Path)
    parser.add_argument("--raw-dir", type=Path)
    parser.add_argument("--window-start", type=date.fromisoformat)
    parser.add_argument("--window-end", type=date.fromisoformat)
    parser.add_argument("--source-state")
    parser.add_argument("--market-reference", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--target-market", required=True)
    parser.add_argument("--target-commodity", required=True)
    parser.add_argument("--price-unit", default="Rs./Quintal")
    parser.add_argument("--pre-event-end", type=date.fromisoformat)
    parser.add_argument("--known-no-data-date", action="append", type=date.fromisoformat, default=[])
    args = parser.parse_args()
    source_count = sum(item is not None for item in (args.report_file, args.report_glob, args.incoming_dir))
    if source_count != 1:
        parser.error("provide exactly one of --report-file, --report-glob, or --incoming-dir")
    reference = load_case_market_snapshot(args.market_reference)
    if args.incoming_dir:
        if not all((args.raw_dir, args.window_start, args.window_end, args.source_state, args.pre_event_end)):
            parser.error("--incoming-dir requires --raw-dir, --window-start, --window-end, --source-state, and --pre-event-end")
        staging = stage_downloaded_reports(args.incoming_dir, args.raw_dir, state=args.source_state, window_start=args.window_start, window_end=args.window_end)
        staged_files = tuple(Path(item["raw_file"]) for item in staging["staged_reports"])
        audit = audit_batch(staged_files, reference=reference, target_market=args.target_market, target_commodity=args.target_commodity, required_price_unit=args.price_unit, pre_event_end=args.pre_event_end, known_no_data_dates=args.known_no_data_date)
        args.output_dir.mkdir(parents=True, exist_ok=True)
        artifacts = write_batch_import_artifacts(staged_files, args.output_dir, reference=reference, target_market=args.target_market, target_commodity=args.target_commodity, required_price_unit=args.price_unit, retrieved_at=datetime.now(timezone.utc))
        output = args.output_dir / "agmarknet-state-daily-batch-coverage.json"
        output.write_text(json.dumps({"staging": staging, "audit": audit}, indent=2, sort_keys=True), encoding="utf-8")
        print(json.dumps({"coverage_file": str(output), "staging": staging, "imported_artifacts": list(artifacts), "audit": audit}, indent=2, sort_keys=True))
        return
    if args.report_glob:
        if args.pre_event_end is None:
            parser.error("--pre-event-end is required with --report-glob")
        files = tuple(Path().glob(args.report_glob))
        if not files:
            parser.error("--report-glob matched no files")
        audit = audit_batch(files, reference=reference, target_market=args.target_market, target_commodity=args.target_commodity, required_price_unit=args.price_unit, pre_event_end=args.pre_event_end, known_no_data_dates=args.known_no_data_date)
        output = args.output_dir / "agmarknet-state-daily-batch-coverage.json"
        args.output_dir.mkdir(parents=True, exist_ok=True)
        artifacts = write_batch_import_artifacts(files, args.output_dir, reference=reference, target_market=args.target_market, target_commodity=args.target_commodity, required_price_unit=args.price_unit, retrieved_at=datetime.now(timezone.utc))
        output.write_text(json.dumps(audit, indent=2, sort_keys=True), encoding="utf-8")
        print(json.dumps({"coverage_file": str(output), "imported_artifacts": list(artifacts), **audit}, indent=2, sort_keys=True))
        return
    assert args.report_file is not None
    report = parse_state_daily_report(args.report_file.read_text(encoding="utf-8"))
    result = import_report(report, reference=reference, target_market=args.target_market, target_commodity=args.target_commodity, required_price_unit=args.price_unit)
    paths = write_import_artifacts(result, args.report_file, args.output_dir, target_market=args.target_market, target_commodity=args.target_commodity, required_price_unit=args.price_unit, retrieved_at=datetime.now(timezone.utc))
    print(json.dumps({**paths, "accepted_rows": len(result.events), "rejected_rows": len(result.rejected), "variety_coverage": coverage_by_variety(result.events)}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
