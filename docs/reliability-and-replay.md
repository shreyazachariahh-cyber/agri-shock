# Reliability, replay, and failure handling

AgriShock emits **market-shock signals** for investigation. Reliability
controls protect lineage and repeatability; they do not turn association into
causation or make an insufficient-evidence result disappear.

## Delivery and replay semantics

| Layer | Repeat behavior | Guarantee / limit |
|---|---|---|
| Kafka/Bronze | Every delivery is retained with topic/partition/offset. | Replaying a source event creates a new raw Kafka delivery by design. Bronze is an audit log, not a deduplicated table. |
| Silver | Source `event_id` is deduplicated by Spark state within the configured event-time watermark and stable checkpoint. | A deleted checkpoint, a changed query identity, or a duplicate older than state retention requires reconciliation; this is not global exactly-once processing. |
| Gold signals | Delta `MERGE` inserts by deterministic `signal_id`. | Replaying the same shock/price identity does not create another Gold signal. A source correction needs a new source/revision identity. |
| Elasticsearch | `_id` equals `signal_id`; repeated indexing overwrites that serving document. | Transient timeout/429/5xx failures use bounded backoff. Validation and permanent 4xx bulk failures remain visible. |

## Dead-letter behavior

Malformed JSON, missing event IDs, invalid event times, and source-specific
payload validation failures do not stop healthy records. Bronze retains the
raw Kafka record independently. The Kafka DLQ payload includes the original
payload, source topic/partition/offset, Kafka timestamp, processing timestamp,
and a machine-readable failure reason. Producer-side normalization DLQ records
also retain original source/event metadata and the raw source record.

If a producer cannot publish its DLQ event after its bounded retry policy, it
raises a visible error; it is not silently counted as handled.

## Late and out-of-order events

`event_time`, not ingestion time, controls Silver deduplication and the
shock-price temporal join. Events within `WATERMARK_HOURS` remain eligible for
stateful processing. Events older than the watermark are still present in
Bronze, but Spark may not update its stateful Silver/Gold outputs for them.
They must go through reconciliation; the project does not claim they were
processed by the live stateful query.

## Reference-data remediation

Market, weather-district, and flood-geometry mappings are never guessed.
Unresolved market rows include `market_reference_not_found`; unresolved weather
and flood rows are written to their respective Silver remediation paths with
reason codes. They are excluded from canonical shock associations until curated
reference data is fixed.

## Restart and checkpoints

Each streaming query has a stable, separate location beneath
`CHECKPOINT_ROOT`. Restart the same query with the same checkpoint and Delta
path to resume offsets/state. Do not share checkpoint directories between
queries. Deleting checkpoints creates a new processing lineage and may replay
source offsets; inspect Bronze and run reconciliation rather than asserting
exactly-once results.

## Historical replay workflow

Use only source-attributed NDJSON explicitly labelled `replayed_historical`.
Each line must carry the standard event envelope and retain the original
`event_time`.

```bash
python -m agri_shock.ingestion.run mandi --mode replay \
  --file /path/to/verified-mandi-history.ndjson --events-per-second 5
```

Run the same command again only to test replay behavior. Expect additional
Bronze Kafka deliveries, no additional Silver logical observation within the
active watermark/checkpoint state, and no duplicate Gold/Elasticsearch signal
for a repeated shock/price identity. After the stream catches up, verify the
Delta/serving contract with:

```bash
python -m agri_shock.runtime.smoke verify \
  --delta-root "$DELTA_ROOT" --elasticsearch-url "$ELASTICSEARCH_URL"
```

For an event older than the watermark, retain the Bronze evidence and schedule
reconciliation. Do not infer a market-shock signal from a dropped late event.
