# Running Spark Structured Streaming

## Prerequisites

- Kafka Compose stack running and `kafka-init` completed.
- Python 3.11 environment with `pip install -e ".[streaming]"`.
- Java 17 exposed through `JAVA_HOME`.
- `WATERMARK_HOURS` explicitly set from documented lateness analysis. The app
  intentionally refuses to start without it.

## Command

```powershell
$env:KAFKA_BOOTSTRAP_SERVERS = "localhost:9092"
$env:WATERMARK_HOURS = "72" # demo value only after recording its rationale
$env:DELTA_ROOT = "data/local/delta"
$env:CHECKPOINT_ROOT = "data/checkpoints"
python -m agri_shock.streaming.app
```

The application remains running until interrupted. It starts independent
checkpointed queries for Bronze raw events, Silver mandi/weather/flood events,
and the Kafka DLQ. Spark uses the event timestamp for deduplication and state;
Kafka timestamps are retained in Bronze for operational audit.

`72` is not a production recommendation. Before a demo claims this setting,
measure `ingestion_time - event_time` from the chosen replay/source and record
the evidence in the engineering decision log.

## Output paths

- `data/local/delta/bronze/raw_events`
- `data/local/delta/silver/mandi_prices`
- `data/local/delta/silver/weather_events`
- `data/local/delta/silver/flood_events`
- `data/checkpoints/*`

The actual Spark/Delta/Kafka execution has not been run on the current host
because its Java, Docker, and Python 3.11 streaming runtime are unavailable.
