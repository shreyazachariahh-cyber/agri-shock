from datetime import datetime, timezone

import pytest

from agri_shock.ingestion.historical_mandi import (
    OGD_RESOURCE_ID, build_ogd_url, convert_records, coverage_report, safe_request_parameters,
)


def _ogd_record(**overrides: object) -> dict[str, object]:
    record: dict[str, object] = {"State": "Kerala", "District": "Ernakulam", "Market": "Aluva", "Commodity": "Banana", "Variety": "Nendran", "Arrival_Date": "01/08/2018", "Min_Price": "1000", "Modal_Price": "1200", "Max_Price": "1400"}
    record.update(overrides)
    return record


def test_ogd_conversion_preserves_variety_in_deterministic_identity() -> None:
    now = datetime(2026, 9, 20, tzinfo=timezone.utc)
    result = convert_records([_ogd_record(), _ogd_record(Variety="Robusta")], now)
    assert len(result.events) == 2
    assert result.events[0].source == "replayed_historical"
    assert result.events[0].payload["price_unit"] == "INR/quintal"
    assert result.events[0].event_id != result.events[1].event_id


def test_ogd_coverage_audit_reports_dates_dimensions_missingness_and_rejections() -> None:
    report = coverage_report([_ogd_record(), _ogd_record(District="", Variety="")])
    assert report["row_count"] == 2
    assert report["accepted_rows"] == 1
    assert report["rejected_rows"] == 1
    assert report["earliest_date"] == "2018-08-01"
    assert report["states"] == ["Kerala"]
    assert report["varieties"] == ["Nendran"]
    assert report["missing_rates"]["District"] == 0.5


def test_ogd_request_requires_key_and_keeps_secret_out_of_manifest_parameters() -> None:
    with pytest.raises(ValueError, match="DATA_GOV_IN_API_KEY"):
        build_ogd_url("")
    url = build_ogd_url("secret", limit=1)
    assert OGD_RESOURCE_ID in url and "api-key=secret" in url
    assert safe_request_parameters(resource_id=OGD_RESOURCE_ID, limit=1, offset=0) == {"resource_id": OGD_RESOURCE_ID, "format": "json", "limit": 1, "offset": 0}
