"""Explicit source-to-envelope normalization. Unknown fields are never guessed."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
import json
from typing import Any, Mapping

from agri_shock.common.events import EventEnvelope, stable_event_id, utc_now
from agri_shock.common.validation import validate_mandi_price


class NormalizationError(ValueError):
    pass


def _required(raw: Mapping[str, Any], field: str) -> str:
    value = str(raw.get(field, "")).strip()
    if not value:
        raise NormalizationError(f"missing_{field.lower().replace(' ', '_')}")
    return value


def _decimal(raw: Any, field: str) -> Decimal:
    try:
        return Decimal(str(raw))
    except (InvalidOperation, ValueError) as error:
        raise NormalizationError(f"invalid_{field}") from error


def _date(raw: str, field: str) -> datetime:
    for pattern in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, pattern).replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    raise NormalizationError(f"invalid_{field}")


def normalize_mandi(
    raw: Mapping[str, Any],
    ingestion_time: datetime | None = None,
    *,
    documented_price_unit: str | None = None,
    source: str = "ogd_agmarknet",
) -> EventEnvelope:
    event_time = _date(_required(raw, "Arrival_Date"), "arrival_date")
    payload = {
        "state": _required(raw, "State"), "district": _required(raw, "District"),
        "market": _required(raw, "Market"), "commodity": _required(raw, "Commodity"),
        "variety": str(raw.get("Variety", "")).strip() or None,
        "min_price": _decimal(raw.get("Min_Price"), "min_price"),
        "modal_price": _decimal(raw.get("Modal_Price"), "modal_price"),
        "max_price": _decimal(raw.get("Max_Price"), "max_price"),
        "price_unit": str(raw.get("Price_Unit") or documented_price_unit or "").strip(),
    }
    if not payload["price_unit"]:
        raise NormalizationError("missing_price_unit")
    result = validate_mandi_price(payload)
    if not result.valid:
        raise NormalizationError(result.reason or "invalid_mandi_price")
    # AGMARKNET can report multiple varieties for one market/commodity/day.
    # Include the normalized variety and unit so they cannot collapse on replay.
    source_key = "|".join((payload["state"], payload["district"], payload["market"], payload["commodity"], payload["variety"] or "", payload["price_unit"], event_time.date().isoformat()))
    return EventEnvelope(stable_event_id(source, source_key, event_time), "mandi_price", event_time, ingestion_time or utc_now(), source, "1.0", payload)


def normalize_weather(raw: Mapping[str, Any], ingestion_time: datetime | None = None) -> EventEnvelope:
    event_time = _date(_required(raw, "Date"), "date")
    district = _required(raw, "District")
    departure = str(raw.get("Daily Departure Per", "")).replace("%", "").strip()
    payload = {
        "state": str(raw.get("State", "")).strip() or None, "district": district,
        "rainfall_actual_mm": _decimal(raw.get("Daily Actual"), "daily_actual"),
        "rainfall_normal_mm": _decimal(raw.get("Daily Normal"), "daily_normal"),
        "rainfall_departure_pct": _decimal(departure, "daily_departure_pct"),
        "rainfall_category": _required(raw, "Daily Category"), "imd_object_id": str(raw.get("OBJ_ID", "")).strip() or None,
    }
    if payload["rainfall_actual_mm"] < 0 or payload["rainfall_normal_mm"] < 0:
        raise NormalizationError("negative_rainfall")
    source_key = f"{payload['imd_object_id'] or district}|{event_time.date().isoformat()}"
    return EventEnvelope(stable_event_id("imd", source_key, event_time), "weather_observation", event_time, ingestion_time or utc_now(), "imd", "1.0", payload)


def normalize_flood(feature: Mapping[str, Any], ingestion_time: datetime | None = None) -> EventEnvelope:
    properties = feature.get("properties")
    geometry = feature.get("geometry")
    if not isinstance(properties, Mapping) or not isinstance(geometry, Mapping):
        raise NormalizationError("invalid_geojson_feature")
    source_id = _required(properties, "eventid")
    event_start = _date(_required(properties, "fromdate"), "fromdate")
    payload = {
        "source_event_id": source_id, "event_start": event_start.isoformat(),
        "event_end": properties.get("todate"), "geometry_json": json.dumps(geometry, sort_keys=True),
        "alert_level": properties.get("alertlevel"), "affected_district_ids": [],
    }
    return EventEnvelope(stable_event_id("gdacs", source_id, event_start), "flood_event", event_start, ingestion_time or utc_now(), "gdacs", "1.0", payload)
