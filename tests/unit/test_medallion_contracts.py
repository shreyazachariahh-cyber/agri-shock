from datetime import datetime, timedelta, timezone

import pytest

from agri_shock.elasticsearch.indexer import validate_document
from agri_shock.processing.confidence import DataConfidence
from agri_shock.processing.evidence import ShockEvidence
from agri_shock.processing.scoring import MarketShockSignal
from agri_shock.storage.medallion import (
    BronzeEvent,
    GoldSignalContext,
    GOLD_SIGNAL_DELTA_COLUMNS,
    GOLD_SIGNAL_DOUBLE_COLUMNS,
    GOLD_SIGNAL_NULLABLE_COLUMNS,
    SilverMandiObservation,
    build_gold_signal,
    deterministic_signal_id,
    gold_signal_delta_row,
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


def test_gold_delta_row_preserves_intentional_null_analytics_for_explicit_schema() -> None:
    """A one-row Spark DataFrame must not infer types from null Gold fields."""
    no_location_context = GoldSignalContext(
        shock_id="weather-2",
        price_event_id="price-2",
        state_id="IN.BR",
        district_id="IN.BR.PATNA",
        market_id="IN.BR.PATNA.M1",
        commodity_id="WHEAT",
        shock_type="rainfall_anomaly",
        shock_time=NOW - timedelta(days=1),
        price_event_time=NOW,
        provenance_type="synthetic_demo",
        source_references=("synthetic-smoke",),
        processing_time=NOW,
    )
    evidence = ShockEvidence(
        "IN.BR.PATNA", "WHEAT", "rainfall_anomaly", 0.5, 800, 1000, -20, None, 1, None
    )
    signal = MarketShockSignal(
        None,
        "INSUFFICIENT_EVIDENCE",
        {},
        DataConfidence(0.2, False, ("insufficient_history",)),
    )

    row = gold_signal_delta_row(build_gold_signal(no_location_context, evidence, signal).to_document())

    assert set(row) == set(GOLD_SIGNAL_DELTA_COLUMNS)
    assert {"location", "robust_z_score", "control_difference_pct", "signal_strength"} <= GOLD_SIGNAL_NULLABLE_COLUMNS
    assert row["location"] is None
    assert row["robust_z_score"] is None
    assert row["control_difference_pct"] is None
    assert row["signal_strength"] is None
    assert row["signal_level"] == "INSUFFICIENT_EVIDENCE"
    assert row["data_confidence"]["reasons"] == ["insufficient_history"]
    assert row["shock_time"] == NOW - timedelta(days=1)
    assert row["processing_time"] == NOW


def test_gold_delta_row_normalizes_integer_numeric_values_for_spark_double_fields() -> None:
    """Regression for live smoke's integer observed_price=800 failure."""
    integer_location_context = GoldSignalContext(
        shock_id="smoke-weather-dhemaji-2024-06-30",
        price_event_id="smoke-mandi-dhemaji-rice-2024-07-01",
        state_id="IN.AS",
        district_id="IN.AS.DHEMAJI",
        market_id="IN.AS.DHEMAJI.M1",
        commodity_id="RICE",
        shock_type="rainfall_anomaly",
        shock_time=NOW - timedelta(days=1),
        price_event_time=NOW,
        provenance_type="synthetic_demo",
        source_references=("synthetic-smoke",),
        processing_time=NOW,
        location={"lat": 27, "lon": 94},
    )
    integer_evidence = ShockEvidence(
        "IN.AS.DHEMAJI", "RICE", "rainfall_anomaly", 1, 800, 1000, -20, -2, 1, -12
    )
    integer_signal = MarketShockSignal(
        80,
        "HIGH",
        {"price_decline": 20, "control_difference": 12},
        DataConfidence(1, True, ()),
    )

    row = gold_signal_delta_row(
        build_gold_signal(integer_location_context, integer_evidence, integer_signal).to_document()
    )

    for column in GOLD_SIGNAL_DOUBLE_COLUMNS:
        assert row[column] is None or isinstance(row[column], float)
    assert row["observed_price"] == 800.0
    assert row["baseline_price"] == 1000.0
    assert row["location"] == {"lat": 27.0, "lon": 94.0}
    assert row["component_scores"] == {"price_decline": 20.0, "control_difference": 12.0}
    assert row["data_confidence"]["value"] == 1.0
    assert isinstance(row["days_after_shock"], int)


def test_late_event_is_preserved_for_reconciliation_not_silently_dropped() -> None:
    cutoff = NOW - timedelta(hours=24)
    assert late_event_disposition(NOW - timedelta(hours=25), cutoff) == "reconcile"
    assert late_event_disposition(cutoff, cutoff) == "process"


def test_late_event_contract_distinguishes_within_and_beyond_72_hour_watermark() -> None:
    cutoff = NOW - timedelta(hours=72)
    assert late_event_disposition(NOW - timedelta(hours=71), cutoff) == "process"
    assert late_event_disposition(NOW - timedelta(hours=73), cutoff) == "reconcile"
