# Local runtime validation (Windows PowerShell)

This runbook validates Kafka to Spark to Delta to Elasticsearch with synthetic
demo events only. It does not validate public-source access, real mandi
observations, or causal claims.

## Prerequisites

- Docker Desktop running; Kafka, Elasticsearch, and Kibana run in Compose.
- Python 3.11, Java 17, and an active project virtual environment.
- Spark runs on the Windows host, not in Docker. Host Spark uses
  `localhost:9092`; Compose services use `kafka:9092` internally.

## Start services

Run from the repository root:

```powershell
docker compose up -d kafka kafka-init elasticsearch kibana
docker compose ps
py -3.11 -m venv .venv-runtime
.\.venv-runtime\Scripts\Activate.ps1
python -m pip install -e ".[dev,streaming]"
```

Set required values in the current PowerShell session:

```powershell
$env:KAFKA_BOOTSTRAP_SERVERS = "localhost:9092"
$env:ELASTICSEARCH_URL = "http://localhost:9200"
$env:DELTA_ROOT = "data/local/smoke-delta"
$env:CHECKPOINT_ROOT = "data/local/smoke-checkpoints"
$env:MARKET_DIMENSION_PATH = "data/local/smoke-reference/market_dimension"
$env:DISTRICT_BOUNDARY_PATH = "data/local/smoke-reference/district_boundaries"
$env:WATERMARK_HOURS = "72"
$env:SHOCK_LOOKAHEAD_DAYS = "14"
```

## Preflight and references

Run preflight first. Every line must say `PASS`; it deliberately fails for
missing Java, non-3.11 Python, Docker, PySpark/Delta/Sedona, services,
configuration, or reference paths.

```powershell
python -m agri_shock.runtime.preflight
python -m agri_shock.runtime.smoke prepare-references `
  --market-dimension $env:MARKET_DIMENSION_PATH `
  --district-boundary $env:DISTRICT_BOUNDARY_PATH
python -m agri_shock.runtime.preflight
```

## Smoke test

In a second PowerShell window, activate the same virtual environment, set the
same environment values, and start Spark. Leave it running:

```powershell
python -m agri_shock.streaming.app
```

In the first window, publish synthetic mandi, weather, and flood events. The
command fails on Kafka delivery failure; it never substitutes an in-memory
publisher.

```powershell
python -m agri_shock.runtime.smoke publish --bootstrap $env:KAFKA_BOOTSTRAP_SERVERS
```

After streaming processes records, materialize the known synthetic Gold signal.
This command refuses to continue unless the expected Gold association exists;
it uses the existing evaluator, writes a Delta Gold signal with deterministic
identity, then indexes that exact document into Elasticsearch.

```powershell
python -m agri_shock.runtime.smoke materialize-gold `
  --delta-root $env:DELTA_ROOT `
  --elasticsearch-url $env:ELASTICSEARCH_URL
python -m agri_shock.runtime.smoke verify `
  --delta-root $env:DELTA_ROOT `
  --elasticsearch-url $env:ELASTICSEARCH_URL
```

The verifier opens each Delta table with Spark and requires the expected
synthetic ID at Bronze raw events, Silver mandi/weather records, Gold
association, and Gold market signal; it then requires the same deterministic
signal ID in Elasticsearch. Repeating publish/materialize/verify must not
create duplicate Gold or serving records.

## Inspect and troubleshoot

Delta paths are below `data/local/smoke-delta/bronze/raw_events`,
`silver/mandi_prices`, `silver/weather_events`, `gold/shock_price_associations`,
and `gold/market_shock_signals`. Inspect raw Kafka coordinates in Bronze,
canonical IDs/provenance in Silver, event-time delay in associations, and
separate `signal_strength`/`data_confidence` in Gold.

Use `Invoke-WebRequest http://localhost:9200/agrishock-market-shock-signals-v1/_count`
and `Start-Process http://localhost:5601` for serving and Kibana inspection.
In Kibana use the Phase 7 `agrishock-signals` data view and filter
`fixture_kind: synthetic_demo`.

If Kafka is unreachable, wait for `kafka-init` in `docker compose ps` and use
`localhost:9092` from the host. If no Gold association exists, verify Spark is
running and all environment values match in both windows. If imports fail, use
Java 17 and Python 3.11 with `.[streaming]` installed. This host has not
live-run the stack; unit tests and preflight are not live integration proof.
