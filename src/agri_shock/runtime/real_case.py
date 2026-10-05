"""Materialize a bounded real historical case without treating it as synthetic."""
from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
import json
from pathlib import Path
from urllib.request import urlopen

from agri_shock.elasticsearch.indexer import ensure_index, index_documents
from agri_shock.processing.confidence import ConfidencePolicy
from agri_shock.processing.real_case import analyze_real_case, read_replayed_events
from agri_shock.processing.scoring import SignalPolicy
from agri_shock.storage.delta import merge_gold_signals
from agri_shock.storage.medallion import gold_signal_delta_row, gold_signal_delta_schema


CASE = {
    "state": "Tamil Nadu", "district": "Vellore", "market": "Vellore APMC",
    "commodity": "Paddy(Common)", "price_unit": "Rs./Quintal",
    "state_id": "in:tn", "district_id": "in:tn:vellore", "market_id": "in:tn:vellore:vellore-apmc",
    "commodity_id": "paddy-common", "window_start": date(2023, 12, 3), "window_end": date(2023, 12, 7),
    "baseline_window_start": date(2022, 12, 1), "baseline_window_end": date(2022, 12, 31),
}
CONFIDENCE_POLICY = ConfidencePolicy(5, 20, 10, 0.2, 0.1)
SIGNAL_POLICY = SignalPolicy(20, 30, 20, 10, 20, 14, 70, 40)


def load_analysis(price_root: Path, environment_file: Path, processing_time: datetime | None = None):
    prices = read_replayed_events(price_root)
    environment = read_replayed_events(environment_file.parent)
    environmental = next((event for event in environment if event.event_type == "flood_event" and event.event_id in environment_file.read_text(encoding="utf-8")), None)
    if environmental is None:
        raise ValueError("environment file did not contain one replayed flood_event")
    case = dict(CASE)
    case["event_window_start"] = case.pop("window_start")
    case["event_window_end"] = case.pop("window_end")
    return analyze_real_case(prices, environmental, confidence_policy=CONFIDENCE_POLICY,
        signal_policy=SIGNAL_POLICY, processing_time=processing_time, **case)


def analysis_report(analysis) -> dict[str, object]:
    document = analysis.gold.to_document()
    return {
        "case": "tamil-nadu-michaung-2023", "classification": "replayed_historical",
        "target_series": {"variety": analysis.selection.selected.variety, "price_unit": analysis.selection.selected.price_unit,
            "historical_count": analysis.selection.historical_count, "event_window_count": analysis.selection.event_window_count},
        "eligible_series": [{"variety": key.variety, "historical_count": historical, "event_window_count": window} for key, historical, window in analysis.selection.eligible],
        "excluded_series": [{"variety": key.variety, "reason": reason} for key, reason in analysis.selection.excluded],
        "baseline": {"median": analysis.baseline.median_price, "mad": analysis.baseline.mad, "sample_size": analysis.baseline.sample_size},
        "target_observation": {"event_id": analysis.target_event.event_id, "event_date": analysis.target_event.event_time.date().isoformat(), "modal_price": analysis.anomaly.observed_price},
        "anomaly": {"deviation_pct": analysis.anomaly.deviation_pct, "robust_z_score": analysis.anomaly.robust_z_score},
        "control_status": analysis.control_status, "environmental_association": analysis.environmental_association,
        "gold_document": document,
    }


def persist_gold(document: dict[str, object], delta_root: Path, elasticsearch_url: str) -> str:
    """Perform the Delta MERGE and idempotent Elasticsearch delivery boundary."""
    from agri_shock.streaming.app import create_smoke_delta_spark
    spark = create_smoke_delta_spark("agrishock-real-case-gold")
    try:
        frame = spark.createDataFrame([gold_signal_delta_row(document)], schema=gold_signal_delta_schema())
        merge_gold_signals(frame, str(delta_root / "gold" / "market_shock_signals"))
        try:
            from elasticsearch import Elasticsearch
        except ImportError as error:
            raise RuntimeError("install agri-shock[streaming] for Delta/Elasticsearch materialization") from error
        client = Elasticsearch(elasticsearch_url)
        ensure_index(client)
        index_documents(client, [document])
        return str(document["signal_id"])
    finally:
        spark.stop()


def verify_persisted(signal_id: str, delta_root: Path, elasticsearch_url: str) -> None:
    """Require exactly one deterministic Gold row and matching serving document."""
    from agri_shock.streaming.app import create_smoke_delta_spark
    spark = create_smoke_delta_spark("agrishock-real-case-verify")
    try:
        path = delta_root / "gold" / "market_shock_signals"
        if not (path / "_delta_log").exists():
            raise RuntimeError("real Gold Delta table is missing")
        count = spark.read.format("delta").load(str(path)).filter(f"signal_id = '{signal_id}'").limit(2).count()
        if count != 1:
            raise RuntimeError(f"expected exactly one real Gold signal {signal_id}, found {count}")
    finally:
        spark.stop()
    response = urlopen(f"{elasticsearch_url.rstrip('/')}/agrishock-market-shock-signals-v1/_doc/{signal_id}", timeout=5).read()
    if signal_id.encode("utf-8") not in response:
        raise RuntimeError("Elasticsearch did not return the deterministic real signal")


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze or materialize the bounded real Vellore historical case")
    parser.add_argument("--price-root", type=Path, required=True)
    parser.add_argument("--environment-file", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True, help="local JSON analysis artifact")
    parser.add_argument("--delta-root", type=Path)
    parser.add_argument("--elasticsearch-url", default="http://localhost:9200")
    parser.add_argument("--materialize", action="store_true", help="MERGE Gold Delta and index Elasticsearch after analysis")
    parser.add_argument("--verify", action="store_true", help="verify the persisted deterministic Gold and Elasticsearch records")
    args = parser.parse_args()
    if (args.materialize or args.verify) and args.delta_root is None:
        parser.error("--materialize/--verify requires --delta-root")
    analysis = load_analysis(args.price_root, args.environment_file)
    report = analysis_report(analysis)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote real historical analysis {args.output}; signal_id={report['gold_document']['signal_id']}")
    if args.materialize:
        print(f"Materialized and indexed real historical Gold signal {persist_gold(report['gold_document'], args.delta_root, args.elasticsearch_url)}")
    if args.verify:
        verify_persisted(str(report["gold_document"]["signal_id"]), args.delta_root, args.elasticsearch_url)
        print(f"Verified real Gold Delta and Elasticsearch signal {report['gold_document']['signal_id']}")


if __name__ == "__main__":
    main()
