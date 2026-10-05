from datetime import date, datetime, timezone

import pytest

from agri_shock.common.events import EventEnvelope
from agri_shock.elasticsearch.indexer import validate_document
from agri_shock.processing.confidence import ConfidencePolicy
from agri_shock.processing.real_case import analyze_real_case, select_series
from agri_shock.processing.scoring import SignalPolicy


POLICY = ConfidencePolicy(5, 20, 10, 0.2, 0.1)
SIGNAL_POLICY = SignalPolicy(20, 30, 20, 10, 20, 14, 70, 40)


def mandi(event_id: str, observed: date, variety: str, price: float, unit: str = "Rs./Quintal") -> EventEnvelope:
    timestamp = datetime.combine(observed, datetime.min.time(), tzinfo=timezone.utc)
    return EventEnvelope(event_id, "mandi_price", timestamp, timestamp, "replayed_historical", "1.0", {
        "state": "Tamil Nadu", "district": "Vellore", "market": "Vellore APMC", "commodity": "Paddy(Common)",
        "variety": variety, "price_unit": unit, "modal_price": price,
    })


def flood() -> EventEnvelope:
    timestamp = datetime(2023, 12, 7, tzinfo=timezone.utc)
    return EventEnvelope("flood-1", "flood_event", timestamp, timestamp, "replayed_historical", "1.1", {
        "event_start": "2023-12-03T00:00:00+00:00", "event_end": "2023-12-07T00:00:00+00:00",
        "geography_basis": "source_reported_district", "inundated_area_hectares": "144", "source_url": "https://ndem.nrsc.gov.in/report.pdf",
    })


def base_events() -> list[EventEnvelope]:
    result = [mandi(f"other-{day}", date(2022, 12, day), "Other", value) for day, value in ((1, 100), (2, 110), (3, 120), (4, 130), (5, 140), (6, 150))]
    result.extend(mandi(f"adt-{day}", date(2022, 12, day), "ADT 37", 1_000) for day in range(1, 6))
    result.extend((mandi("other-event", date(2023, 12, 4), "Other", 80), mandi("adt-event", date(2023, 12, 4), "ADT 37", 1)))
    return result


def select(events: list[EventEnvelope]):
    return select_series(events, state="Tamil Nadu", district="Vellore", market="Vellore APMC", commodity="Paddy(Common)",
        price_unit="Rs./Quintal", event_window_start=date(2023, 12, 3), event_window_end=date(2023, 12, 7), minimum_baseline_observations=5,
        baseline_window_start=date(2022, 12, 1), baseline_window_end=date(2022, 12, 31))


def test_selection_uses_coverage_then_lexical_tie_not_price_outcome() -> None:
    selected = select(base_events())
    assert selected.selected.variety == "Other"
    # Reversing the event prices cannot change a coverage-only choice.
    changed = [mandi(item.event_id, item.event_time.date(), item.payload["variety"], 99_999 if item.event_time.year == 2023 else item.payload["modal_price"], item.payload["price_unit"]) for item in base_events()]
    assert select(changed).selected == selected.selected


def test_selection_requires_minimum_baseline_and_never_pools_varieties() -> None:
    selected = select(base_events())
    assert {key.variety for key, _, _ in selected.eligible} == {"ADT 37", "Other"}
    sparse = [item for item in base_events() if item.payload["variety"] != "Other"]
    assert select(sparse).selected.variety == "ADT 37"
    insufficient = [item for item in sparse if item.event_time.year != 2022 or item.event_time.day < 5]
    with pytest.raises(ValueError, match="no series"):
        select(insufficient)


def test_incompatible_units_are_rejected_not_combined() -> None:
    events = base_events() + [mandi("bundle", date(2023, 12, 4), "Bundle variety", 1, "Rs./Bundle")]
    selected = select(events)
    assert any(key.variety == "Bundle variety" and reason == "incompatible_price_unit" for key, reason in selected.excluded)


def test_real_case_uses_median_mad_and_preserves_missing_control() -> None:
    analysis = analyze_real_case(base_events(), flood(), state="Tamil Nadu", district="Vellore", market="Vellore APMC", commodity="Paddy(Common)",
        price_unit="Rs./Quintal", state_id="in:tn", district_id="in:tn:vellore", market_id="in:tn:vellore:vellore-apmc", commodity_id="paddy-common",
        event_window_start=date(2023, 12, 3), event_window_end=date(2023, 12, 7), baseline_window_start=date(2022, 12, 1), baseline_window_end=date(2022, 12, 31), confidence_policy=POLICY, signal_policy=SIGNAL_POLICY,
        processing_time=datetime(2026, 1, 1, tzinfo=timezone.utc))
    assert analysis.baseline.median_price == 125
    assert analysis.baseline.mad == 15
    assert analysis.anomaly.deviation_pct == -36
    assert analysis.anomaly.robust_z_score is not None
    document = analysis.gold.to_document()
    assert document["fixture_kind"] == "replayed_historical"
    assert document["control_difference_pct"] is None
    assert "control_comparison_unavailable" in document["confidence_reasons"]
    assert document["shock_severity"] == 0
    assert document["signal_id"] == analysis.gold.signal_id
    assert any(reference.startswith("baseline_event_ids_sha256:") for reference in document["source_references"])


def test_zero_mad_is_explicitly_unscored_for_robust_component() -> None:
    events = [mandi(f"same-{day}", date(2022, 12, day), "Other", 100) for day in range(1, 6)] + [mandi("event", date(2023, 12, 4), "Other", 80)]
    analysis = analyze_real_case(events, flood(), state="Tamil Nadu", district="Vellore", market="Vellore APMC", commodity="Paddy(Common)",
        price_unit="Rs./Quintal", state_id="in:tn", district_id="in:tn:vellore", market_id="in:tn:vellore:vellore-apmc", commodity_id="paddy-common",
        event_window_start=date(2023, 12, 3), event_window_end=date(2023, 12, 7), baseline_window_start=date(2022, 12, 1), baseline_window_end=date(2022, 12, 31), confidence_policy=POLICY, signal_policy=SIGNAL_POLICY)
    assert analysis.anomaly.robust_z_score is None
    assert analysis.signal.component_scores["robust_abnormality"] == 0


def test_real_gold_id_is_replay_stable_and_elasticsearch_compatible() -> None:
    kwargs = dict(state="Tamil Nadu", district="Vellore", market="Vellore APMC", commodity="Paddy(Common)",
        price_unit="Rs./Quintal", state_id="in:tn", district_id="in:tn:vellore", market_id="in:tn:vellore:vellore-apmc", commodity_id="paddy-common",
        event_window_start=date(2023, 12, 3), event_window_end=date(2023, 12, 7), baseline_window_start=date(2022, 12, 1), baseline_window_end=date(2022, 12, 31),
        confidence_policy=POLICY, signal_policy=SIGNAL_POLICY)
    first = analyze_real_case(base_events(), flood(), processing_time=datetime(2026, 1, 1, tzinfo=timezone.utc), **kwargs).gold.to_document()
    replay = analyze_real_case(base_events(), flood(), processing_time=datetime(2026, 1, 2, tzinfo=timezone.utc), **kwargs).gold.to_document()
    assert first["signal_id"] == replay["signal_id"]
    assert validate_document(first)["fixture_kind"] == "replayed_historical"
