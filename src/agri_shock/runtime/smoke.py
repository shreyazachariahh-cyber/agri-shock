"""Synthetic local-stack smoke helpers; no command reports success on a missing stage."""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Mapping
from urllib.request import urlopen

from agri_shock.common.events import EventEnvelope
from agri_shock.elasticsearch.indexer import ensure_index, index_documents
from agri_shock.ingestion.publisher import KafkaJsonPublisher
from agri_shock.processing.confidence import ConfidencePolicy, EvidenceQuality, assess_confidence
from agri_shock.processing.evidence import ShockEvidence
from agri_shock.processing.scoring import SignalPolicy, evaluate_signal
from agri_shock.storage.delta import merge_gold_signals
from agri_shock.storage.medallion import (
    GoldSignalContext,
    build_gold_signal,
    deterministic_signal_id,
    gold_signal_delta_row,
    gold_signal_delta_schema,
)


SMOKE_SHOCK_ID = "smoke-weather-dhemaji-2024-06-30"
SMOKE_PRICE_EVENT_ID = "smoke-mandi-dhemaji-rice-2024-07-01"


@dataclass(frozen=True, slots=True)
class SmokePaths:
    delta_root: Path

    @property
    def required_tables(self) -> tuple[Path, ...]:
        return (
            self.delta_root / "bronze" / "raw_events",
            self.delta_root / "silver" / "mandi_prices",
            self.delta_root / "silver" / "weather_events",
            self.delta_root / "gold" / "shock_price_associations",
            self.delta_root / "gold" / "market_shock_signals",
        )


def expected_signal_id() -> str:
    return deterministic_signal_id(SMOKE_SHOCK_ID, SMOKE_PRICE_EVENT_ID)


def synthetic_events() -> tuple[tuple[str, EventEnvelope], ...]:
    """Known synthetic records; never use these as real agricultural observations."""
    observed_at = datetime(2024, 7, 1, tzinfo=timezone.utc)
    ingested_at = datetime(2024, 7, 2, tzinfo=timezone.utc)
    return (
        ("mandi-prices", EventEnvelope(SMOKE_PRICE_EVENT_ID, "mandi_price", observed_at, ingested_at, "synthetic_demo", "1.0", {"state": "Assam", "district": "Dhemaji", "market": "Dhemaji Demo Mandi", "commodity": "rice", "variety": "demo", "min_price": 700, "modal_price": 800, "max_price": 900, "price_unit": "INR/quintal"})),
        ("weather-events", EventEnvelope(SMOKE_SHOCK_ID, "weather_observation", observed_at - timedelta(days=1), ingested_at, "synthetic_demo", "1.0", {"state": "Assam", "district": "Dhemaji", "rainfall_actual_mm": 80, "rainfall_normal_mm": 20, "rainfall_departure_pct": 300, "rainfall_category": "LD", "imd_object_id": "demo-dhemaji"})),
        ("flood-events", EventEnvelope("smoke-flood-dhemaji-2024-06-30", "flood_event", observed_at - timedelta(days=1), ingested_at, "synthetic_demo", "1.0", {"source_event_id": "smoke-flood-dhemaji-2024-06-30", "event_start": "2024-06-30T00:00:00+00:00", "event_end": None, "alert_level": "demo", "geometry_json": "{\"type\":\"Point\",\"coordinates\":[94.59,27.48]}"})),
    )


def publish_synthetic_events(bootstrap_servers: str, publisher: Any | None = None) -> int:
    producer = publisher or KafkaJsonPublisher(bootstrap_servers)
    events = synthetic_events()
    for topic, event in events:
        producer.publish(topic, event.event_id, event)
    return len(events)


def verify_delta_layout(paths: SmokePaths) -> None:
    missing = [str(path) for path in paths.required_tables if not (path / "_delta_log").exists()]
    if missing:
        raise RuntimeError(f"smoke test incomplete; missing Delta table paths: {', '.join(missing)}")


def verify_delta_content(paths: SmokePaths) -> None:
    """Read Delta tables and require the known synthetic IDs at every stage."""
    from agri_shock.streaming.app import create_smoke_delta_spark

    verify_delta_layout(paths)
    spark = create_smoke_delta_spark("agrishock-smoke-verify")
    try:
        checks = (
            (paths.delta_root / "bronze" / "raw_events", f"source_event_id = '{SMOKE_PRICE_EVENT_ID}'", "Bronze mandi event", False),
            (paths.delta_root / "silver" / "mandi_prices", f"event_id = '{SMOKE_PRICE_EVENT_ID}'", "Silver mandi event", True),
            (paths.delta_root / "silver" / "weather_events", f"event_id = '{SMOKE_SHOCK_ID}'", "Silver weather event", True),
            # A single price can legitimately associate with more than one shock
            # type. The Gold association identity is the composite key below.
            (paths.delta_root / "gold" / "shock_price_associations", f"shock_id = '{SMOKE_SHOCK_ID}' AND price_event_id = '{SMOKE_PRICE_EVENT_ID}'", "Gold association", True),
            (paths.delta_root / "gold" / "market_shock_signals", f"signal_id = '{expected_signal_id()}'", "Gold signal", True),
        )
        for path, predicate, label, must_be_unique in checks:
            matches = spark.read.format("delta").load(str(path)).filter(predicate).limit(2).count()
            if matches < 1 or must_be_unique and matches != 1:
                expected_count = "exactly one" if must_be_unique else "at least one"
                raise RuntimeError(f"smoke test incomplete; expected {expected_count} {label}, found {matches}")
    finally:
        spark.stop()


def verify_elasticsearch_signal(url: str, signal_id: str, fetch: Callable[[str], bytes] | None = None) -> None:
    request = f"{url.rstrip('/')}/agrishock-market-shock-signals-v1/_doc/{signal_id}"
    body = fetch(request) if fetch else urlopen(request, timeout=5).read()
    if signal_id.encode() not in body:
        raise RuntimeError(f"Elasticsearch did not return expected signal_id {signal_id}")


def prepare_synthetic_reference_data(market_dimension_path: Path, district_boundary_path: Path) -> None:
    """Create a labelled demo-only reference pair required by the streaming join."""
    from agri_shock.streaming.app import create_smoke_delta_spark

    spark = create_smoke_delta_spark("agrishock-smoke-reference-data")
    try:
        spark.createDataFrame([
            ("IN.AS.DHEMAJI.M1", "IN.AS.DHEMAJI", "IN.AS", "Assam", "Dhemaji", "Dhemaji Demo Mandi"),
        ], ["market_id", "district_id", "state_id", "source_state", "source_district", "source_market"]).write.format("delta").mode("overwrite").save(str(market_dimension_path))
        spark.createDataFrame([
            ("IN.AS.DHEMAJI", "Assam", "Dhemaji", "{\"type\":\"Polygon\",\"coordinates\":[[[94.4,27.3],[94.8,27.3],[94.8,27.7],[94.4,27.7],[94.4,27.3]]]}")
        ], ["district_id", "source_state", "source_district", "geometry_json"]).write.format("delta").mode("overwrite").save(str(district_boundary_path))
    finally:
        spark.stop()


def create_gold_signal_dataframe(spark: Any, document: Mapping[str, Any]) -> Any:
    """Create one canonical Gold row with an explicit nullable-aware schema."""
    return spark.createDataFrame(
        [gold_signal_delta_row(document)], schema=gold_signal_delta_schema()
    )


def materialize_synthetic_gold(delta_root: Path, elasticsearch_url: str) -> str:
    """Create and serve one labelled synthetic Gold signal after association exists."""
    from agri_shock.streaming.app import create_smoke_delta_spark

    association_path = delta_root / "gold" / "shock_price_associations"
    if not (association_path / "_delta_log").exists():
        raise RuntimeError("no Gold shock-price association exists; start streaming and publish smoke events first")
    spark = create_smoke_delta_spark("agrishock-smoke-gold")
    try:
        association = spark.read.format("delta").load(str(association_path)).filter(
            "shock_id = 'smoke-weather-dhemaji-2024-06-30' AND price_event_id = 'smoke-mandi-dhemaji-rice-2024-07-01'"
        ).limit(1).collect()
        if not association:
            raise RuntimeError("no expected synthetic association exists; inspect Silver mapping/event-time configuration")
        signal = evaluate_signal(
            ShockEvidence("IN.AS.DHEMAJI", "RICE", "rainfall_anomaly", 1.0, 800, 1000, -20, -2.0, 1, -12),
            assess_confidence(EvidenceQuality(20, 10, 0, 0, True, True, True, True), ConfidencePolicy(5, 20, 10, 0.2, 0.1)),
            SignalPolicy(20, 30, 20, 10, 20, 14, 70, 40),
        )
        context = GoldSignalContext(
            shock_id=SMOKE_SHOCK_ID, price_event_id=SMOKE_PRICE_EVENT_ID,
            state_id="IN.AS", district_id="IN.AS.DHEMAJI", market_id="IN.AS.DHEMAJI.M1", commodity_id="RICE",
            shock_type="rainfall_anomaly", shock_time=datetime(2024, 6, 30, tzinfo=timezone.utc),
            price_event_time=datetime(2024, 7, 1, tzinfo=timezone.utc), provenance_type="synthetic_demo",
            source_references=("synthetic-smoke",), processing_time=datetime.now(timezone.utc),
            display_state="Assam", display_district="Dhemaji", display_market="Dhemaji Demo Mandi", display_commodity="rice",
            location={"lat": 27.48, "lon": 94.59},
        )
        document = build_gold_signal(context, ShockEvidence("IN.AS.DHEMAJI", "RICE", "rainfall_anomaly", 1.0, 800, 1000, -20, -2.0, 1, -12), signal).to_document()
        gold_path = delta_root / "gold" / "market_shock_signals"
        # Do not infer schema from a single document: valid Gold fields can be
        # null and a sufficient signal can have empty confidence-reason arrays.
        gold_frame = create_gold_signal_dataframe(spark, document)
        merge_gold_signals(gold_frame, str(gold_path))
        try:
            from elasticsearch import Elasticsearch
        except ImportError as error:
            raise RuntimeError("Gold Delta write succeeded but Elasticsearch client is missing; install agri-shock[streaming]") from error
        client = Elasticsearch(elasticsearch_url)
        ensure_index(client)
        index_documents(client, [document])
        return document["signal_id"]
    finally:
        spark.stop()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run or verify AgriShock synthetic smoke stages")
    subparsers = parser.add_subparsers(dest="command", required=True)
    publish = subparsers.add_parser("publish", help="publish synthetic Kafka events")
    publish.add_argument("--bootstrap", default="localhost:9092")
    verify = subparsers.add_parser("verify", help="verify materialized Delta paths and Elasticsearch signal")
    verify.add_argument("--delta-root", type=Path, required=True)
    verify.add_argument("--elasticsearch-url", default="http://localhost:9200")
    references = subparsers.add_parser("prepare-references", help="write synthetic Delta reference dimensions")
    references.add_argument("--market-dimension", type=Path, required=True)
    references.add_argument("--district-boundary", type=Path, required=True)
    materialize = subparsers.add_parser("materialize-gold", help="materialize and index the synthetic Gold signal")
    materialize.add_argument("--delta-root", type=Path, required=True)
    materialize.add_argument("--elasticsearch-url", default="http://localhost:9200")
    args = parser.parse_args()
    if args.command == "publish":
        print(f"Published {publish_synthetic_events(args.bootstrap)} synthetic events")
    elif args.command == "verify":
        verify_delta_content(SmokePaths(args.delta_root))
        verify_elasticsearch_signal(args.elasticsearch_url, expected_signal_id())
        print(f"Verified Delta paths and Elasticsearch signal {expected_signal_id()}")
    elif args.command == "prepare-references":
        prepare_synthetic_reference_data(args.market_dimension, args.district_boundary)
        print("Wrote synthetic Delta reference dimensions")
    else:
        print(f"Materialized and indexed synthetic Gold signal {materialize_synthetic_gold(args.delta_root, args.elasticsearch_url)}")


if __name__ == "__main__":
    main()
