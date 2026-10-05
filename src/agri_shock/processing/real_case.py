"""Outcome-independent analysis of a bounded, replayed historical case.

This module deliberately knows nothing about a particular district or price
outcome.  It selects a comparable *series* using identity, unit, coverage and
event-window presence only, then applies the project's existing seasonal
median/MAD implementation.  It is intentionally separate from Spark so its
scientific choices can be unit tested without a running local stack.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Iterable, Mapping
import json

from agri_shock.common.events import EventEnvelope
from agri_shock.processing.analytics import Baseline, PriceAnomaly, PriceObservation, price_anomaly, seasonal_baseline
from agri_shock.processing.confidence import ConfidencePolicy, EvidenceQuality, assess_confidence
from agri_shock.processing.evidence import ShockEvidence
from agri_shock.processing.scoring import MarketShockSignal, SignalPolicy, evaluate_signal
from agri_shock.storage.medallion import GoldSignalContext, GoldMarketShockSignal, build_gold_signal


@dataclass(frozen=True, slots=True)
class SeriesKey:
    state: str
    district: str
    market: str
    commodity: str
    variety: str
    price_unit: str


@dataclass(frozen=True, slots=True)
class SeriesSelection:
    selected: SeriesKey
    historical_count: int
    event_window_count: int
    eligible: tuple[tuple[SeriesKey, int, int], ...]
    excluded: tuple[tuple[SeriesKey, str], ...]


@dataclass(frozen=True, slots=True)
class RealCaseAnalysis:
    selection: SeriesSelection
    baseline: Baseline
    anomaly: PriceAnomaly
    target_event: EventEnvelope
    signal: MarketShockSignal
    gold: GoldMarketShockSignal
    control_status: str
    environmental_association: str


def _event_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def read_replayed_events(root: Path) -> tuple[EventEnvelope, ...]:
    """Read labelled replay files, deduplicating identical event identifiers.

    A conflicting duplicate is rejected rather than allowing a replay artifact
    to silently alter the historical input.
    """
    records: dict[str, EventEnvelope] = {}
    for path in sorted(root.rglob("*.replayed.ndjson")):
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            raw = json.loads(line)
            event = EventEnvelope(
                raw["event_id"], raw["event_type"], _event_datetime(raw["event_time"]),
                _event_datetime(raw["ingestion_time"]), raw["source"], raw["schema_version"], raw["payload"],
            )
            if event.source != "replayed_historical":
                raise ValueError(f"{path}:{line_number} is not labelled replayed_historical")
            existing = records.get(event.event_id)
            if existing is not None and existing != event:
                raise ValueError(f"conflicting replay events share event_id {event.event_id}")
            records[event.event_id] = event
    return tuple(records[key] for key in sorted(records))


def mandi_series_key(event: EventEnvelope, *, state: str, district: str) -> SeriesKey:
    if event.event_type != "mandi_price":
        raise ValueError("expected mandi_price event")
    payload = event.payload
    required = ("market", "commodity", "variety", "price_unit")
    if any(not str(payload.get(field, "")).strip() for field in required):
        raise ValueError("mandi event lacks series identity")
    if str(payload.get("state", "")).strip() != state:
        raise ValueError("mandi event state does not match the case")
    if str(payload.get("district", "")).strip() != district:
        raise ValueError("mandi event district does not match the case")
    return SeriesKey(state, district, str(payload["market"]), str(payload["commodity"]), str(payload["variety"]), str(payload["price_unit"]))


def select_series(
    events: Iterable[EventEnvelope], *, state: str, district: str, market: str,
    commodity: str, price_unit: str, event_window_start: date, event_window_end: date,
    minimum_baseline_observations: int, baseline_window_start: date, baseline_window_end: date,
) -> SeriesSelection:
    """Select before prices are inspected: maximum historical coverage then variety.

    A series needs the fixed market/commodity/unit identity, at least one
    observation in the declared event window, and the existing minimum number
    of historical observations in the same calendar month before that window.
    No price movement participates in this decision.
    """
    grouped: dict[SeriesKey, list[EventEnvelope]] = {}
    for event in events:
        if event.event_type != "mandi_price":
            continue
        key = mandi_series_key(event, state=state, district=district)
        if key.market == market and key.commodity == commodity:
            grouped.setdefault(key, []).append(event)

    eligible: list[tuple[SeriesKey, int, int]] = []
    excluded: list[tuple[SeriesKey, str]] = []
    for key, series_events in sorted(grouped.items(), key=lambda item: item[0].variety.casefold()):
        if key.price_unit != price_unit:
            excluded.append((key, "incompatible_price_unit"))
            continue
        historical = [item for item in series_events if baseline_window_start <= item.event_time.date() <= baseline_window_end]
        event_count = sum(event_window_start <= item.event_time.date() <= event_window_end for item in series_events)
        if event_count == 0:
            excluded.append((key, "not_observed_in_event_window"))
        elif len(historical) < minimum_baseline_observations:
            excluded.append((key, "insufficient_historical_baseline"))
        else:
            eligible.append((key, len(historical), event_count))
    if not eligible:
        raise ValueError("no series meets fixed identity, coverage, unit, and baseline requirements")
    # Coverage descending, followed by casefolded variety name: deterministic,
    # outcome-independent, and not a price/anomaly ranking.
    winner = sorted(eligible, key=lambda item: (-item[1], item[0].variety.casefold()))[0]
    return SeriesSelection(winner[0], winner[1], winner[2], tuple(eligible), tuple(excluded))


def analyze_real_case(
    price_events: Iterable[EventEnvelope], environmental_event: EventEnvelope, *,
    state: str, district: str, market: str, commodity: str, price_unit: str,
    state_id: str, district_id: str, market_id: str, commodity_id: str,
    event_window_start: date, event_window_end: date,
    baseline_window_start: date, baseline_window_end: date,
    confidence_policy: ConfidencePolicy, signal_policy: SignalPolicy,
    processing_time: datetime | None = None,
) -> RealCaseAnalysis:
    """Build one honest Gold-ready result; unavailable control evidence stays null."""
    events = tuple(price_events)
    selection = select_series(events, state=state, district=district, market=market, commodity=commodity,
        price_unit=price_unit, event_window_start=event_window_start, event_window_end=event_window_end,
        minimum_baseline_observations=confidence_policy.minimum_baseline_observations,
        baseline_window_start=baseline_window_start, baseline_window_end=baseline_window_end)
    chosen = [item for item in events if item.event_type == "mandi_price" and mandi_series_key(item, state=state, district=district) == selection.selected]
    historical = [PriceObservation(item.event_time.date(), float(item.payload["modal_price"])) for item in chosen if baseline_window_start <= item.event_time.date() <= baseline_window_end]
    # Earliest available event-window observation is predeclared and independent
    # of price value; it is not a maximum-decline selection.
    targets = sorted((item for item in chosen if event_window_start <= item.event_time.date() <= event_window_end), key=lambda item: (item.event_time, item.event_id))
    target = targets[0]
    baseline = seasonal_baseline(historical, target.event_time.date(), confidence_policy.minimum_baseline_observations)
    if baseline is None:
        raise ValueError("selection invariant violated: baseline became insufficient")
    anomaly = price_anomaly(float(target.payload["modal_price"]), baseline)
    payload = environmental_event.payload
    event_start = _event_datetime(str(payload["event_start"])).date()
    days_after = (target.event_time.date() - event_start).days
    if days_after < 0:
        raise ValueError("target observation precedes authoritative shock window")
    control_status = "unavailable_no_authoritative_unaffected_market_evidence"
    duplicate_rate = 0.0  # read_replayed_events has already rejected conflicting duplicate IDs.
    confidence = assess_confidence(EvidenceQuality(
        baseline.sample_size, len({item.observation_date for item in historical}), 0.0, duplicate_rate,
        True, False, True, True,
    ), confidence_policy)
    # 144 ha is preserved in provenance but cannot be interpreted as [0,1]
    # severity.  A zero contribution is deliberately conservative, not a claim
    # that no flooding occurred.
    evidence = ShockEvidence(district_id, commodity_id, "flood", 0.0, anomaly.observed_price,
        anomaly.baseline_price, anomaly.deviation_pct, anomaly.robust_z_score, days_after, None)
    signal = evaluate_signal(evidence, confidence, signal_policy)
    baseline_event_ids = tuple(sorted(item.event_id for item in chosen if baseline_window_start <= item.event_time.date() <= baseline_window_end))
    baseline_lineage = sha256("|".join(baseline_event_ids).encode("utf-8")).hexdigest()
    reference = (
        f"environmental_event_id:{environmental_event.event_id}",
        f"environmental_association:{payload.get('geography_basis')}",
        f"environmental_observed_inundation_hectares:{payload.get('inundated_area_hectares')}",
        f"environmental_source:{payload.get('source_url')}",
        f"price_series_variety:{selection.selected.variety}",
        f"price_unit:{selection.selected.price_unit}",
        "price_provider:Directorate of Marketing & Inspection (AGMARKNET 2.0)",
        f"price_target_event_id:{target.event_id}",
        f"baseline_period:{baseline_window_start.isoformat()}:{baseline_window_end.isoformat()}",
        f"baseline_observations:{baseline.sample_size}",
        f"baseline_event_ids_sha256:{baseline_lineage}",
        f"control_status:{control_status}",
    )
    context = GoldSignalContext(environmental_event.event_id, target.event_id, state_id, district_id, market_id,
        commodity_id, "flood", datetime.combine(event_start, datetime.min.time(), tzinfo=timezone.utc),
        target.event_time, "replayed_historical", reference, processing_time or datetime.now(timezone.utc),
        state, district, market, commodity, None)
    return RealCaseAnalysis(selection, baseline, anomaly, target, signal, build_gold_signal(context, evidence, signal), control_status, str(payload.get("geography_basis")))
