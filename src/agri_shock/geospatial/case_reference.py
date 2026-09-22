"""Validation for narrowly scoped, authoritative case-study market references."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlparse


class CaseReferenceError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class MarketResolution:
    status: str
    record: Mapping[str, Any] | None
    reason: str | None


def _required(record: Mapping[str, Any], field: str) -> str:
    value = str(record.get(field, "")).strip()
    if not value:
        raise CaseReferenceError(f"missing_{field}")
    return value


def validate_case_market_snapshot(snapshot: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    """Validate exact, provenance-backed mappings without fuzzy matching."""
    if snapshot.get("reference_scope") != "case-study reference data":
        raise CaseReferenceError("invalid_reference_scope")
    records = snapshot.get("markets")
    if not isinstance(records, list) or not records:
        raise CaseReferenceError("missing_markets")
    keys: set[tuple[str, str]] = set()
    validated: list[Mapping[str, Any]] = []
    for record in records:
        if not isinstance(record, Mapping):
            raise CaseReferenceError("invalid_market_record")
        state = _required(record, "source_state")
        market = _required(record, "source_market")
        for field in ("source_district", "state_id", "district_id", "market_id", "evidence_url", "retrieved_at"):
            _required(record, field)
        parsed = urlparse(str(record["evidence_url"]))
        if parsed.scheme != "https" or parsed.hostname != "agmarknet.gov.in":
            raise CaseReferenceError("unsupported_market_evidence_url")
        key = (state.upper(), market.upper())
        if key in keys:
            raise CaseReferenceError("ambiguous_state_market_mapping")
        keys.add(key)
        validated.append(record)
    return tuple(validated)


def load_case_market_snapshot(path: Path) -> tuple[Mapping[str, Any], ...]:
    return validate_case_market_snapshot(json.loads(path.read_text(encoding="utf-8")))


def resolve_market_district(
    state: str, market: str, reference: tuple[Mapping[str, Any], ...],
) -> MarketResolution:
    """Return a mapping only for one exact state/market match in its stated scope."""
    matches = [record for record in reference if str(record["source_state"]).strip().upper() == state.strip().upper() and str(record["source_market"]).strip().upper() == market.strip().upper()]
    if not matches:
        return MarketResolution("unresolved", None, "case_reference_not_found")
    if len(matches) != 1:
        return MarketResolution("unresolved", None, "ambiguous_case_reference")
    return MarketResolution("resolved", matches[0], None)
