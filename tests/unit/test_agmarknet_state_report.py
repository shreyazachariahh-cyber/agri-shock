from datetime import datetime, timezone

from agri_shock.geospatial.case_reference import validate_case_market_snapshot
from agri_shock.ingestion.agmarknet_state_report import import_report, parse_state_daily_report

CSV = '''"Market-wise, Commodity-wise Daily Report for a State/UT on 04-Dec-2023 State/UT : Tamil Nadu"

Commodity,Arrivals,Unit of Arrivals,Variety,Minimum Prices,Maximum Prices,Modal Prices,Unit of Price
Market Name : Vellore APMC
Commodity Group Name : Cereals
Paddy(Common),4.43,Metric Tonnes,ADT 37,1346.0,1346.0,1346.0,Rs./Quintal
,,Metric Tonnes,Other,2993.0,2993.0,2993.0,Rs./Quintal
'''


def _reference():
    return validate_case_market_snapshot({"reference_scope": "case-study reference data", "markets": [{"source_state": "Tamil Nadu", "source_district": "Vellore", "source_market": "Vellore APMC", "state_id": "in:tn", "district_id": "in:tn:vellore", "market_id": "in:tn:vellore:vellore-apmc", "evidence_url": "https://agmarknet.gov.in/viewmarketprofileinputpublic", "retrieved_at": "2026-09-22T00:00:00Z"}]})


def test_parser_carries_only_explicit_market_and_commodity_context() -> None:
    report = parse_state_daily_report(CSV)
    assert report.arrival_date == "04/12/2023"
    assert [row["Commodity"] for row in report.rows] == ["Paddy(Common)", "Paddy(Common)"]
    assert report.rows[1]["Arrivals"] is None
    assert [row["Variety"] for row in report.rows] == ["ADT 37", "Other"]


def test_import_keeps_varieties_separate_and_requires_scoped_geography() -> None:
    result = import_report(parse_state_daily_report(CSV), reference=_reference(), target_market="Vellore APMC", target_commodity="Paddy(Common)", required_price_unit="Rs./Quintal", retrieved_at=datetime(2026, 9, 22, tzinfo=timezone.utc))
    assert len(result.events) == 2 and not result.rejected
    assert {event.payload["variety"] for event in result.events} == {"ADT 37", "Other"}
    assert len({event.event_id for event in result.events}) == 2
    assert {event.payload["district"] for event in result.events} == {"Vellore"}
    assert {event.payload["price_unit"] for event in result.events} == {"Rs./Quintal"}


def test_import_rejects_incompatible_unit_without_a_synthetic_conversion() -> None:
    report = parse_state_daily_report(CSV.replace("Rs./Quintal\n", "Rs./Bundle\n", 1))
    result = import_report(report, reference=_reference(), target_market="Vellore APMC", target_commodity="Paddy(Common)", required_price_unit="Rs./Quintal")
    assert len(result.events) == 1
    assert result.rejected[0]["reason"] == "incompatible_price_unit"
