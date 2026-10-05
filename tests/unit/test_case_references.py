import json

from agri_shock.runtime.case_references import case_reference_rows


def test_bounded_case_reference_requires_exact_district_feature(tmp_path) -> None:
    snapshot = tmp_path / "markets.json"
    boundary = tmp_path / "boundary.geojson"
    snapshot.write_text(json.dumps({"reference_scope": "case-study reference data", "markets": [{"source_state": "Tamil Nadu", "source_district": "Vellore", "source_market": "Vellore APMC", "state_id": "in:tn", "district_id": "in:tn:vellore", "market_id": "in:tn:vellore:vellore-apmc", "evidence_url": "https://agmarknet.gov.in/viewmarketprofileinputpublic", "retrieved_at": "2026-09-22T00:00:00Z"}]}), encoding="utf-8")
    boundary.write_text(json.dumps({"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {"STATE": "Tamil Nadu", "DISTRICT": "Vellore"}, "geometry": {"type": "Polygon", "coordinates": [[[79, 12], [80, 12], [80, 13], [79, 12]]]}}]}), encoding="utf-8")
    markets, districts = case_reference_rows(snapshot, boundary)
    assert markets[0][0] == "in:tn:vellore:vellore-apmc"
    assert districts[0][0] == "in:tn:vellore"
