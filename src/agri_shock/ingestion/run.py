"""Run a configured live source adapter or labelled replay against Kafka."""
from __future__ import annotations
import argparse
import os
from pathlib import Path
from agri_shock.ingestion.base import RetryPolicy
from agri_shock.ingestion.flood_producer import FloodProducer
from agri_shock.ingestion.mandi_producer import MandiProducer
from agri_shock.ingestion.publisher import KafkaJsonPublisher
from agri_shock.ingestion.replay import replay
from agri_shock.ingestion.weather_producer import WeatherProducer

LIVE_URL_ENV = {"mandi": "MANDI_API_URL", "weather": "IMD_API_URL", "flood": "GDACS_API_URL"}
PRODUCER = {"mandi": MandiProducer, "weather": WeatherProducer, "flood": FloodProducer}

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", choices=("mandi", "weather", "flood"))
    parser.add_argument("--mode", choices=("live", "replay"), required=True)
    parser.add_argument("--file", type=Path)
    parser.add_argument("--events-per-second", type=float, default=1.0)
    args = parser.parse_args()
    publisher = KafkaJsonPublisher(os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"))
    if args.mode == "replay":
        if args.file is None:
            parser.error("--file is required in replay mode")
        print(f"Replayed {replay(args.file, publisher, PRODUCER[args.source].topic, args.events_per_second)} labelled event(s).")
        return
    url = os.getenv(LIVE_URL_ENV[args.source])
    if not url:
        parser.error(f"{LIVE_URL_ENV[args.source]} is required in live mode")
    report = PRODUCER[args.source](publisher, RetryPolicy()).fetch_and_ingest(url)
    print(f"Published={report.published} rejected={report.rejected}")

if __name__ == "__main__":
    main()
