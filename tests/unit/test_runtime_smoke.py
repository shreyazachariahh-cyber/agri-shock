from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
import sys

import pytest

from agri_shock.ingestion.publisher import MemoryPublisher
from agri_shock.processing.confidence import DataConfidence
from agri_shock.processing.evidence import ShockEvidence
from agri_shock.processing.scoring import MarketShockSignal
from agri_shock.runtime.smoke import (
    SmokePaths,
    create_gold_signal_dataframe,
    expected_signal_id,
    publish_synthetic_events,
    synthetic_events,
    verify_delta_layout,
    verify_elasticsearch_signal,
)
from agri_shock.streaming import app as streaming_app
from agri_shock.storage.medallion import (
    GoldSignalContext,
    build_gold_signal,
)


def test_synthetic_smoke_events_cover_all_ingestion_topics_and_publish() -> None:
    topics = {topic for topic, _ in synthetic_events()}
    assert topics == {"mandi-prices", "weather-events", "flood-events"}
    publisher = MemoryPublisher()
    assert publish_synthetic_events("unused", publisher) == 3
    assert len(publisher.messages) == 3


def test_expected_signal_id_is_deterministic() -> None:
    assert expected_signal_id() == expected_signal_id()


def test_delta_only_smoke_session_avoids_streaming_packages_and_is_single_partition(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Builder:
        def __init__(self) -> None:
            self.master_value: str | None = None
            self.options: dict[str, str] = {}

        def master(self, value: str) -> "Builder":
            self.master_value = value
            return self

        def config(self, key: str, value: str) -> "Builder":
            self.options[key] = value
            return self

    builder = Builder()
    configured: list[Builder] = []
    expected_spark = object()

    def configure_delta(input_builder: Builder) -> SimpleNamespace:
        configured.append(input_builder)
        return SimpleNamespace(getOrCreate=lambda: expected_spark)

    monkeypatch.setattr(streaming_app, "_delta_builder", lambda _: builder)
    monkeypatch.setitem(sys.modules, "delta", SimpleNamespace(configure_spark_with_delta_pip=configure_delta))

    assert streaming_app.create_smoke_delta_spark("smoke") is expected_spark
    assert configured == [builder]
    assert builder.master_value == "local[1]"
    assert builder.options == {
        "spark.sql.shuffle.partitions": "1",
        "spark.default.parallelism": "1",
        "spark.ui.enabled": "false",
    }


def test_delta_layout_requires_all_transaction_logs(tmp_path: Path) -> None:
    paths = SmokePaths(tmp_path)
    with pytest.raises(RuntimeError, match="missing Delta table paths"):
        verify_delta_layout(paths)
    for table in paths.required_tables:
        (table / "_delta_log").mkdir(parents=True)
    verify_delta_layout(paths)


def test_elasticsearch_verification_requires_the_expected_id() -> None:
    signal_id = expected_signal_id()
    verify_elasticsearch_signal("http://example.test", signal_id, lambda _: f'{{"_id":"{signal_id}"}}'.encode())
    with pytest.raises(RuntimeError, match="did not return"):
        verify_elasticsearch_signal("http://example.test", signal_id, lambda _: b'{"found":false}')


def test_gold_materialization_uses_explicit_schema_for_nullable_contract_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    """Regression: Spark must not infer nulls or empty arrays from one row."""
    now = datetime(2024, 7, 2, tzinfo=timezone.utc)
    document = build_gold_signal(
        GoldSignalContext(
            shock_id="shock-nullable",
            price_event_id="price-nullable",
            state_id="IN.BR",
            district_id="IN.BR.PATNA",
            market_id="IN.BR.PATNA.M1",
            commodity_id="WHEAT",
            shock_type="rainfall_anomaly",
            shock_time=now,
            price_event_time=now,
            provenance_type="synthetic_demo",
            source_references=("synthetic-smoke",),
            processing_time=now,
            location=None,
        ),
        ShockEvidence("IN.BR.PATNA", "WHEAT", "rainfall_anomaly", 0.5, 800, 1000, -20, None, 1, None),
        MarketShockSignal(50.0, "MEDIUM", {}, DataConfidence(0.9, True, ())),
    ).to_document()
    explicit_schema = object()
    monkeypatch.setattr("agri_shock.runtime.smoke.gold_signal_delta_schema", lambda: explicit_schema)

    class RecordingSpark:
        def createDataFrame(self, rows: list[dict[str, object]], *, schema: object) -> str:
            self.rows = rows
            self.schema = schema
            return "typed-gold-frame"

    spark = RecordingSpark()
    assert create_gold_signal_dataframe(spark, document) == "typed-gold-frame"
    assert spark.schema is explicit_schema
    assert spark.rows[0]["location"] is None
    assert spark.rows[0]["robust_z_score"] is None
    assert spark.rows[0]["control_difference_pct"] is None
    assert spark.rows[0]["confidence_reasons"] == []
    assert spark.rows[0]["data_confidence"]["reasons"] == []
