# Local runtime validation (Windows PowerShell and WSL2)

This runbook validates Kafka to Spark to Delta to Elasticsearch with synthetic
demo events only. It does not validate public-source access, real mandi
observations, or causal claims.

## Windows Spark runtime choice

- Docker Desktop running; Kafka, Elasticsearch, and Kibana run in Compose.
- Python 3.11, Java 17, and an active project virtual environment. The
  `streaming` dependency extra installs pandas because the Sedona/PySpark
  runtime imports it; no separate manual pandas installation is required.

### Recommended: run Spark in WSL2

Native Windows Hadoop requires `winutils.exe` for the PySpark/Hadoop local-file
path. AgriShock does **not** download or distribute this executable because an
unverified binary would be a supply-chain risk. The project-supported path is
WSL2/Linux, where that Windows helper is not required.

Open an Administrator PowerShell and run:

```powershell
wsl --install -d Ubuntu
```

Restart if Windows requests it, launch Ubuntu once to create a Linux user, then
clone/open the repository inside the Linux filesystem (for example,
`~/src/agri-shock`) and follow the same Python 3.11/Java 17 commands there.
Docker Desktop must have WSL integration enabled for Ubuntu. Linux Spark uses
`localhost:9092` and `localhost:9200` when Docker Desktop exposes the ports.
Microsoft documents `wsl --install` as the supported installation path for
Windows 10 version 2004+ and Windows 11.

### Direct native Windows Spark: only with an approved helper

Direct Windows is not the recommended project runtime. Use it only when your
organization provides a Hadoop **3.3.4** `winutils.exe` through its approved
software distribution or an internally reproducible build process. Do not
download an arbitrary helper from GitHub.

Before running Spark, set `HADOOP_HOME` to the parent containing
`bin\winutils.exe`, create a manifest from
`config/windows-hadoop-helper.example.json`, fill in the artifact path and the
SHA-256 from `Get-FileHash`, then set:

```powershell
$env:HADOOP_HOME = "C:\approved-hadoop-3.3.4"
$env:AGRISHOCK_WINUTILS_MANIFEST = "C:\approved-hadoop-3.3.4\agrishock-winutils.json"
```

Preflight verifies the path, Hadoop version declaration, artifact path, and
SHA-256 before any SparkContext is created. A missing or unverifiable helper
is a hard failure with a WSL2 recommendation.

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

In a second terminal in the selected supported runtime (WSL2 recommended),
activate the same virtual environment, set the same environment values, and
start Spark. Leave it running:

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

The materialization and verification commands use a separate Delta-only local
Spark session (`local[1]`, one shuffle partition). They deliberately do not
load Kafka or Sedona because the active streaming process already owns those
resources. These smoke-only settings do not change production stream settings
or Gold semantics.

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
`localhost:9092` from the host/WSL runtime. If no Gold association exists,
verify Spark is running and all environment values match in both terminals. If
preflight reports `windows-hadoop`, use WSL2 or obtain an organization-approved
and checksummed helper; do not bypass the check. If imports fail, use Java 17
and Python 3.11 with `.[streaming]` installed. The synthetic smoke path and
the separate bounded Vellore replay were live-validated in WSL2; that evidence
does not make a different host's preflight or unit tests equivalent to live
integration proof.
