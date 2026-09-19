"""Read-only local Delta/Elasticsearch operational health summary."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.request import urlopen

from agri_shock.common.observability import summarize_health
from agri_shock.streaming.contracts import DLQ_DELTA_RELATIVE_PATH


TABLES = {
    "events_ingested": "bronze/raw_events",
    "silver_mandi": "silver/mandi_prices",
    "silver_weather": "silver/weather_events",
    "dlq_events": DLQ_DELTA_RELATIVE_PATH,
    "unresolved_mappings": "silver/unresolved_market_mappings",
    "gold_associations": "gold/shock_price_associations",
    "gold_signals": "gold/market_shock_signals",
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Read Delta counts and serving status without mutating data")
    parser.add_argument("--delta-root", type=Path, required=True)
    parser.add_argument("--elasticsearch-url", default="http://localhost:9200")
    parser.add_argument("--max-dlq-rate", type=float, default=0.05)
    args = parser.parse_args()
    from agri_shock.streaming.app import create_smoke_delta_spark

    spark = create_smoke_delta_spark("agrishock-health")
    try:
        counts: dict[str, int] = {}
        for metric, relative_path in TABLES.items():
            path = args.delta_root / relative_path
            counts[metric] = spark.read.format("delta").load(str(path)).count() if (path / "_delta_log").exists() else 0
        try:
            with urlopen(f"{args.elasticsearch_url.rstrip('/')}/agrishock-market-shock-signals-v1/_count", timeout=5) as response:
                counts["elasticsearch_signals"] = int(json.loads(response.read())["count"])
        except Exception:
            counts["elasticsearch_signals"] = -1
        summary = summarize_health(counts, args.max_dlq_rate)
        print(json.dumps({"counts": summary.counts, "warnings": summary.warnings}, sort_keys=True))
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
