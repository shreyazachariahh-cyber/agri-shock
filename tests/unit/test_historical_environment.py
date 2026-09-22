from datetime import datetime, timezone
from pathlib import Path

import pytest

from agri_shock.geospatial.case_reference import (
    CaseReferenceError,
    load_case_market_snapshot,
    resolve_market_district,
    validate_case_market_snapshot,
)
from agri_shock.ingestion.historical_environment import (
    convert_ndem_extract,
    normalize_ndem_district_flood,
)
from agri_shock.ingestion.normalizers import NormalizationError


def ndem_record(**overrides: str) -> dict[str, str]:
    record = {
        "source_provider": "National Remote Sensing Centre, ISRO",
        "source_report_title": "Flood / Rain affected areas during Michaung Cyclone in Parts of TAMILNADU State",
        "source_url": "https://ndem.nrsc.gov.in/documents/report.pdf",
        "artifact_sha256": "a" * 64,
        "map_id": "2023/CY/TN/01a/07122023",
        "state": "Tamil Nadu",
        "district": "Vellore",
        "observation_date": "2023-12-07",
        "event_window_start": "2023-12-03",
        "event_window_end": "2023-12-07",
        "inundated_area_hectares": "144",
    }
    record.update(overrides)
    return record


def test_ndem_adapter_preserves_district_provenance_and_replay_identity() -> None:
    time = datetime(2026, 9, 22, tzinfo=timezone.utc)
    first = normalize_ndem_district_flood(ndem_record(), time)
    second = normalize_ndem_district_flood(ndem_record(), time)
    assert first.event_id == second.event_id
    assert first.source == "replayed_historical"
    assert first.payload["reported_district"] == "Vellore"
    assert first.payload["geometry_json"] is None
    assert first.payload["event_time_precision"] == "day"
    assert first.payload["inundated_area_hectares"] == "144"
    assert first.payload["severity_basis"] is None


@pytest.mark.parametrize("overrides,reason", [
    ({"district": ""}, "missing_district"),
    ({"inundated_area_hectares": "-1"}, "negative_inundated_area_hectares"),
    ({"severity": "high"}, "unsupported_severity_field"),
    ({"source_url": "https://example.com/report.pdf"}, "unsupported_authoritative_source_url"),
    ({"event_window_end": "2023-12-02"}, "invalid_event_window"),
])
def test_ndem_adapter_rejects_unsupported_or_malformed_source_data(overrides: dict[str, str], reason: str) -> None:
    with pytest.raises(NormalizationError, match=reason):
        normalize_ndem_district_flood(ndem_record(**overrides))


def test_ndem_batch_preserves_rejected_rows() -> None:
    events, report = convert_ndem_extract([ndem_record(), ndem_record(district="")])
    assert len(events) == report.accepted == 1
    assert report.rejected[0]["reason"] == "missing_district"
    assert report.rejected[0]["raw_record"]["district"] == ""


def case_snapshot() -> dict[str, object]:
    return {
        "reference_scope": "case-study reference data",
        "markets": [{
            "source_state": "Tamil Nadu", "source_district": "Vellore", "source_market": "Vellore APMC",
            "state_id": "in:tn", "district_id": "in:tn:vellore", "market_id": "in:tn:vellore:vellore-apmc",
            "evidence_url": "https://agmarknet.gov.in/viewmarketprofileinputpublic",
            "retrieved_at": "2026-09-22T00:00:00+00:00",
        }],
    }


def test_case_market_reference_resolves_only_exact_authoritative_mapping() -> None:
    reference = validate_case_market_snapshot(case_snapshot())
    resolved = resolve_market_district("Tamil Nadu", "Vellore APMC", reference)
    missing = resolve_market_district("Tamil Nadu", "Unverified Market", reference)
    assert resolved.status == "resolved"
    assert resolved.record and resolved.record["district_id"] == "in:tn:vellore"
    assert missing.status == "unresolved"
    assert missing.reason == "case_reference_not_found"


def test_versioned_vellore_case_snapshot_is_valid_and_scoped() -> None:
    path = Path("data/case_studies/tamil-nadu-michaung-2023/market-reference.v1.json")
    reference = load_case_market_snapshot(path)
    result = resolve_market_district("Tamil Nadu", "Vellore APMC", reference)
    assert len(reference) == 1
    assert result.status == "resolved"
    assert result.record and result.record["source_district"] == "Vellore"


def test_case_market_reference_rejects_ambiguous_or_unsupported_evidence() -> None:
    snapshot = case_snapshot()
    snapshot["markets"] = snapshot["markets"] * 2  # type: ignore[index]
    with pytest.raises(CaseReferenceError, match="ambiguous_state_market_mapping"):
        validate_case_market_snapshot(snapshot)
    snapshot = case_snapshot()
    snapshot["markets"][0]["evidence_url"] = "https://example.com/market"  # type: ignore[index]
    with pytest.raises(CaseReferenceError, match="unsupported_market_evidence_url"):
        validate_case_market_snapshot(snapshot)
