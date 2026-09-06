from datetime import datetime, timedelta, timezone

import pytest

from agri_shock.elasticsearch.indexer import validate_document
from agri_shock.processing.confidence import DataConfidence
from agri_shock.processing.evidence import ShockEvidence
from agri_shock.processing.scoring import MarketShockSignal
from agri_shock.storage.medallion import (
    BronzeEvent,
    GoldSignalContext,
    SilverMandiObservation,
    build_gold_signal,
    deterministic_signal_id,
    late_event_disposition,
)


NOW = datetime(2024, 7, 2, tzinfo=timezone.utc)


def context() -> GoldSignalContext:
    return GoldSignalContext(
        shock_id="flood-1",
        price_event_id="price-1",
        state_id="IN.AS",
        district_id="IN.AS.DHEMAJI",
        market_id="IN.AS.DHEMAJI.M1",
        commodity_id="RICE",
        shock_type="flood",
        shock_time=NOW - timedelta(days=1),
        price_event_time=NOW,
        provenance_type="replayed_historical",
        source_references=("GDACS-1102678", "AGMARKNET-EXTRACT-1"),
        processing_time=NOW,
        display_state="Assam",
        display_district="Dhemaji",
        display_market="Demo Mandi",
        display_commodity="Rice",
        location={"lat": 27.48, "lon": 94.59},
    )


def test_signal_id_is_deterministic_and_changes_for_a_new_price_revision() -> None:
    first = deterministic_signal_id("flood-1", "price-1")
    assert first == deterministic_signal_id("flood-1", "price-1")
    assert first != deterministic_signal_id("flood-1", "price-1-revision-2")


def test_bronze_preserves_raw_kafka_provenance_and_event_time() -> None:
    bronze = BronzeEvent(
        raw_payload='{"event_id":"price-1"}',
        kafka_topic="mandi-prices",
        kafka_partition=2,
        kafka_offset=17,
        kafka_timestamp=NOW,
        ingestion_time=NOW,
        source_event_time=NOW - timedelta(days=1),
        source="agmarknet",
        source_event_id="price-1",
        schema_version="1.0",
    )
    assert bronze.raw_payload.startswith("{")
    assert bronze.kafka_offset == 17
    assert bronze.source_event_time == NOW - timedelta(days=1)


def test_malformed_silver_observation_is_rejected_without_a_mapping() -> None:
    with pytest.raises(ValueError, match="missing canonical"):
        SilverMandiObservation(
            event_id="price-1",
            event_time=NOW,
            ingestion_time=NOW,
            source="agmarknet",
            state_id="IN.AS",
            district_id="",
            market_id="IN.AS.DHEMAJI.M1",
            commodity_id="RICE",
            modal_price=100.0,
            kafka_topic="mandi-prices",
            kafka_partition=0,
            kafka_offset=1,
            raw_event_id="price-1",
            geography_mapping_version="districts-2024-01",
        )


def test_gold_document_preserves_event_time_provenance_and_elasticsearch_compatibility() -> None:
    evidence = ShockEvidence(
        "IN.AS.DHEMAJI", "RICE", "flood", 0.8, 800, 1000, -20, -2, 1, -12
    )
    signal = MarketShockSignal(
        75.0,
        "HIGH",
        {"price_decline": 20.0},
        DataConfidence(0.8, True, ("control_comparison_unavailable",)),
    )
    gold = build_gold_signal(context(), evidence, signal)
    document = gold.to_document()
    assert document["signal_id"] == deterministic_signal_id("flood-1", "price-1")
    assert document["shock_time"] == "2024-07-01T00:00:00+00:00"
    assert document["price_event_time"] == "2024-07-02T00:00:00+00:00"
    assert document["source_references"] == ["GDACS-1102678", "AGMARKNET-EXTRACT-1"]
    assert validate_document(document)["district_id"] == "IN.AS.DHEMAJI"


def test_late_event_is_preserved_for_reconciliation_not_silently_dropped() -> None:
    cutoff = NOW - timedelta(hours=24)
    assert late_event_disposition(NOW - timedelta(hours=25), cutoff) == "reconcile"
    assert late_event_disposition(cutoff, cutoff) == "process"
