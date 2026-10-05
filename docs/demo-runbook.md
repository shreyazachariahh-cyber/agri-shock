# Recruiter demo runbook

This end-to-end demo is a reproducible **synthetic replay**. It demonstrates
the platform contracts and operating path; it does not demonstrate real mandi
prices, observed agricultural impact, or causal inference.

## Scenario fixture

[`data/sample/market_shock_signals.ndjson`](../data/sample/market_shock_signals.ndjson)
contains ten `synthetic_demo` documents across two districts and commodities
in each scenario. The numerical values are invented. The state/event labels
provide varied replay context only:

| Context label | Public context reference | Fixture use |
|---|---|---|
| Assam floods | [GDACS flood FL 1102678](https://www.gdacs.org/report.aspx?episodeid=15&eventid=1102678&eventtype=FL) | Flood association display |
| Bihar floods | [GDACS flood FL 1103434](https://www.gdacs.org/Floods/report.aspx?episodeid=23&eventid=1103434&eventtype=FL) | Flood association display |
| Kerala floods | [GDACS/ECHO 2018 Kerala context](https://www.gdacs.org/report.aspx?episodeid=4&eventid=1000529&eventtype=TC) | Historical flood-context display |
| Maharashtra drought | [IMD Annual Report 2023](https://mausam.imd.gov.in/imd_latest/contents/ar2023.pdf) | Dry-weather context display |
| Himachal Pradesh landslides | [GDACS India monsoon report](https://www.gdacs.org/report.aspx?episodeid=15&eventid=1102678&eventtype=FL) | Landslide-context display |

These links establish only that public event/weather context exists. They do
not validate the scenario coordinates, dates, markets, commodities, prices,
or signals. Those must be replaced by source-attributed, versioned data before
any real case-study claim.

## Architecture exercised

```text
Weather or flood event
        │ (event time + geometry)
        ▼
Canonical district / market association
        │ (configured temporal lookahead)
        ▼
MarketShockSignal + data confidence
        │ (stable signal_id; replay idempotency)
        ▼
Elasticsearch: agrishock-market-shock-signals-v1
        ▼
Kibana: map, trend, explanation and confidence panels
```

For a production run, Spark Structured Streaming materializes the upstream
Bronze/Silver/Gold tables. The fixture begins at the Gold document boundary so
the dashboard can be demonstrated even where source APIs or Spark runtime are
not available.

## Run locally

1. Use Python 3.11 and Java 17 for the full Spark runtime. This synthetic
   fixture remains separate from the Phase 13D replayed-historical Vellore
   validation and its primary dashboard.
2. Copy `.env.example` to `.env`, set the Kafka/Spark reference-data variables
   required for streaming, and start the observability services:

   ```powershell
   docker compose up -d kafka kafka-init elasticsearch kibana
   ```

3. Wait until Elasticsearch returns a healthy response:

   ```powershell
   Invoke-WebRequest http://localhost:9200
   ```

4. Install the optional delivery client and index the demo fixture:

   ```powershell
   python -m pip install -e ".[streaming]"
   python -m agri_shock.elasticsearch.indexer data/sample/market_shock_signals.ndjson
   ```

   Without Elasticsearch, this dependency-free contract check remains useful:

   ```powershell
   python -m agri_shock.elasticsearch.indexer data/sample/market_shock_signals.ndjson --validate-only
   ```

5. Open `http://localhost:5601`, create the `agrishock-signals` data view for
   `agrishock-market-shock-signals-*`, and select `event_time` as its time
   field. Build the panels in [the dashboard specification](../dashboards/kibana/README.md).
6. Add `fixture_kind: synthetic_demo` as a global dashboard filter. It is a
   safety guard for the demo; never remove it while presenting fixture output.

To prove index delivery, run:

```powershell
Invoke-WebRequest "http://localhost:9200/agrishock-market-shock-signals-v1/_count"
```

The expected document count for this fixture is 10. Re-running the indexer
updates the same stable `signal_id` documents rather than creating duplicates.

## Screenshot checklist

No dashboard screenshot is committed because Kibana was not runnable on this
host. After completing the local run, capture and add the following PNGs under
`dashboards/screenshots/`:

1. `01-map.png`: map filtered to `fixture_kind: synthetic_demo`, colored by
   maximum `signal_strength` and sized by document count.
2. `02-signal-ranking.png`: district/commodity ranking with HIGH/MEDIUM/LOW
   split and visible `data_confidence.value`.
3. `03-explanation.png`: selected record table with baseline, observed price,
   deviation, control difference, component scores, and confidence reasons.

Label every capture **Synthetic demo data — not a real market finding**.
