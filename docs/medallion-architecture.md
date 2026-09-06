# Delta Lake medallion architecture

AgriShock uses Delta Lake as the system of record. Kafka is the transport;
Elasticsearch is a serving projection. Neither replaces Delta lineage.

```text
Kafka event → Bronze raw_events → Silver validated/canonical tables
           → Gold shock_price_associations → Gold market_shock_signals
           → Elasticsearch market-shock-signals index
```

## Bronze: `bronze/raw_events`

Bronze is append-only capture before semantic validation or deduplication. Its
deterministic Kafka identity is `(kafka_topic, kafka_partition, kafka_offset)`.
It retains `raw_payload`, key, topic, partition, offset, Kafka timestamp,
Bronze ingestion timestamp, extracted source event time, source event ID, event
type, source, and source schema version. Extraction is metadata only: raw JSON
is never rewritten. This table is the audit/replay input for malformed records
as well as valid records.

It is partitioned by Kafka topic and source event date to keep investigation
and replay reads bounded. A missing source event time lands in a null partition
rather than being invented.

## Silver: validated and canonical

| Dataset | Deterministic key | Event time | Canonical/provenance fields |
|---|---|---|---|
| `silver/mandi_prices` | source `event_id` | `event_time` | state/district/market mapping, commodity ID, Kafka coordinates, raw payload pointer, source/schema version |
| `silver/weather_events` | source `event_id` | `event_time` | canonical district lookup outcome, IMD attributes, Kafka coordinates, source/schema version |
| `silver/flood_events` | source `event_id` | `event_time` / event start | source event ID, geometry, alert metadata, Kafka coordinates, source/schema version |
| `silver/unresolved_market_mappings` | source `event_id` | `event_time` | unresolved source market fields and Kafka/source provenance for reference-data remediation |
| reference dimensions | versioned source keys | validity interval | canonical IDs, aliases/boundary or mapping version, source provenance |

Source-specific schemas are explicit. Invalid JSON, invalid timestamps,
impossible price ordering, and missing required fields route to the DLQ with a
reason. Canonical mapping is an explicit reference-table or spatial operation;
an unresolved match is not guessed. Statefully deduplicated Silver streams use
`event_id` and configured event-time watermarks. Kafka coordinates and raw
payload provenance are retained so a data-quality decision can be audited.

## Gold: analytical contracts

### `gold/shock_price_associations`

One row represents a canonical district shock and price observation whose
`price_event_time` lies in the configured post-shock event-time window. Its
logical key is `(shock_id, price_event_id)`. It retains `state_id`,
`district_id`, `market_id`, `commodity_id`, `shock_type`, `shock_time`,
`price_event_time`, `days_after_shock`, spatial relationship, severity and
source references.

### `gold/market_shock_signals`

`GoldMarketShockSignal` is the contract shared by Delta and Elasticsearch. Its
deterministic `signal_id` is SHA-256 of `shock_id`, `price_event_id`, and the
model-contract version. It preserves canonical IDs; observed/baseline prices;
deviation, robust z-score, delay, shock severity and control difference;
component scores; `signal_strength`; `signal_level`; independent
`data_confidence` and reasons; provenance type; source references; processing
time; and model-contract version.

`signal_strength` is never multiplied by confidence. `INSUFFICIENT_EVIDENCE`
has no numeric strength. A Gold signal serializes through
`GoldMarketShockSignal.to_document()` and is then validated by the Phase 7
Elasticsearch indexer; there is no separate dashboard schema.

## Delta semantics, checkpoints, and corrections

- Every streaming sink has a deterministic path under `DELTA_ROOT` and a
  dedicated checkpoint under `CHECKPOINT_ROOT`; checkpoint paths must never be
  shared by unrelated queries.
- Bronze uses Delta append. It does not remove duplicates because Kafka
  coordinates are evidence.
- Silver uses append plus stateful `event_id` deduplication within the chosen
  watermark horizon. Delta transaction logs and stable checkpoint state make a
  restarted query replay-safe for that query/checkpoint pair; this project does
  not claim global exactly-once delivery if checkpoints are deleted, query
  identities change, or a source changes an old record in place.
- Gold association/signal outputs use their logical deterministic identities.
  Signal delivery must use Delta `MERGE`/idempotent insert by `signal_id` when
  materialized from a batch boundary (`merge_gold_signals`). Replaying the same
  input therefore does not create an uncontrolled new signal.
- A source correction must carry a new source event/revision identity. It
  yields a new association/signal lineage rather than silently overwriting an
  earlier finding. Supersession metadata is a future source-contract addition.
- Events older than the stream watermark remain preserved in Bronze. They are
  sent to reconciliation rather than silently becoming a stateful Silver/Gold
  update. Periodic batch reconciliation recomputes the affected logical keys.
- Schema evolution is additive only for Bronze/Silver/Gold minor versions.
  Renames, semantic type changes, and analytical changes require a new
  model-contract version and serving index version, with migration/backfill
  documented before activation.

## Serving boundary

The Phase 7 index is `agrishock-market-shock-signals-v1`. Its strict mapping
includes all Gold canonical IDs, event times, analytical measures, provenance,
contract version, and separate confidence fields. Its `_id` is `signal_id`, so
replay delivery is idempotent at the serving boundary too.
