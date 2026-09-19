# Operations and performance

Run preflight, then start the Compose services and streaming app as documented
in `runtime-validation.md`. Inspect a live query through Spark's
`lastProgress`: batch ID, input rows/rates, trigger duration, watermark, and
state-operator metrics are reported by Spark itself. Do not substitute these
fields with estimated values.

Read-only health summary:

```bash
python -m agri_shock.runtime.health --delta-root "$DELTA_ROOT" --elasticsearch-url "$ELASTICSEARCH_URL"
```

It counts existing Delta layers, including durable `silver/dlq_events`, and Elasticsearch documents, then emits warning
codes for configured DLQ-rate and unresolved-geography conditions. Missing
optional remediation tables count as zero; an unavailable Elasticsearch count
is `-1`, not a successful result.

Benchmark publisher dispatch only (not Spark throughput):

```bash
python -m agri_shock.runtime.benchmark --events 100 --sink kafka --bootstrap "$KAFKA_BOOTSTRAP_SERVERS"
python -m agri_shock.runtime.benchmark --events 10000 --duplicate-every 100 --sink kafka --bootstrap "$KAFKA_BOOTSTRAP_SERVERS"
```

The emitted JSON measures submitted events, elapsed wall time, dispatch
throughput, and deliberate duplicate count. It does not claim Kafka consumer,
Spark, Delta, or Elasticsearch end-to-end latency. No benchmark results are
committed until these commands run in WSL.

Likely unmeasured bottlenecks: Kafka partition skew by market, Spark state
growth from watermark duration, Sedona/reference joins, small Delta files, and
Elasticsearch bulk/shard pressure. Scale only after measurement: increase
partitioning and Spark parallelism deliberately, compact Delta files under a
separate maintenance policy, broadcast small versioned references when proven
safe, and tune Elasticsearch bulk size/shards from observed rejections and
latency.
