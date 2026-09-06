# Engineering decisions

## Event envelope and idempotency

- **Problem:** source retries can duplicate observations.
- **Choice:** deterministic SHA-256 IDs based on source, stable source key, and
  event time; preserve the original source ID when present.
- **Trade-off:** a source correction with the same key/time needs an explicit
  revision/version field rather than silently overwriting history.

## Kafka partitioning

- **Choice:** prices by market locality, weather by district locality, flood by
  source event, and alerts by district/commodity.
- **Why:** ordering is meaningful within each analytical entity but a global key
  would cause avoidable skew.
- **Trade-off:** large markets may need measured, deterministic salting later.

## Kafka listeners and topic bootstrap

- **Problem:** the former single advertised address `kafka:9092` was reachable
  only from containers; Windows clients could bootstrap through a mapped port
  but then receive unreachable broker metadata.
- **Choice:** `INTERNAL://kafka:9092` for Compose clients and
  `EXTERNAL://localhost:9092` for host clients, plus an idempotent
  `kafka-init` service.
- **Trade-off:** this is a single-node, plaintext local setup. Production needs
  multiple brokers, TLS/SASL, ACLs, replication, and external DNS addresses.
- **Naming:** new output topic is `market-shock-signals`; this safer term does
  not assert farmer distress or causal attribution.

## No default watermark

- **Choice:** `watermark_hours` is unset in Phase 1.
- **Why:** a duration without source-lateness evidence would be arbitrary.
- **Next:** record observed source/fixture lateness, choose per-stream
  percentiles plus operational margin, and document beyond-watermark handling.

## Signal strength is separate from data confidence

- **Problem:** a single "distress score" obscures uncertainty and suggests a
  causal conclusion the data cannot establish.
- **Choice:** emit a `MarketShockSignal` with an additive, configured
  `signal_strength` (0–100) and an independent `data_confidence` value plus
  machine-readable reasons. Critical failures—missing canonical geography,
  shock time, required fields, or a minimum historical baseline—produce
  `INSUFFICIENT_EVIDENCE` instead of a numeric result.
- **Why:** reviewers can distinguish strong statistical co-occurrence from
  reliable evidence. A missing control comparison reduces confidence but does
  not erase the observed local movement.
- **Trade-off:** the provisional contribution caps (20/30/20/10/20) and
  thresholds are transparent configuration rather than calibrated truth. They
  require future evaluation against a documented, representative dataset.
- **Naming:** this replaces distress-oriented analytical naming. It is a market
  shock signal, never evidence of farmer distress, exploitation, or causation.

## Elasticsearch delivery uses a strict, versioned document contract

- **Problem:** dashboards need low-latency filter, map, and aggregation fields
  without re-implementing Gold-table semantics in every visualization.
- **Choice:** index signal documents into the versioned
  `agrishock-market-shock-signals-v1` index, keyed by stable `signal_id`.
  Mapping is strict; identifiers are keywords, event fields are dates,
  coordinates are `geo_point`, and score components are flattened fields.
- **Why:** stable IDs make replay delivery idempotent, and a strict mapping
  catches contract drift before it becomes dashboard ambiguity.
- **Trade-off:** the Phase 7 fixture enters at the Gold-to-Elasticsearch
  boundary and is explicitly synthetic because a local cluster and verified
  source-attributed historical market series were unavailable. It proves the
  delivery interface, not a live end-to-end service run.

## Runtime matrix

- **Problem:** Spark, Delta, Kafka connectors, Java, and Python must be aligned
  before a real streaming service is built.
- **Choice:** Python 3.11, Java 17, Spark/PySpark 3.5.6, Scala 2.12, Delta
  3.2.1, and `spark-sql-kafka-0-10_2.12:3.5.6`; keep Kafka 3.8.0 and
  Elasticsearch/Kibana 8.15.2 together.
- **Why:** Spark 3.5.6 is the maintained 3.5 release; Delta documents 3.2.x ↔
  Spark 3.5.x compatibility. Python 3.11 is deliberately chosen for the Spark
  runtime because PySpark 3.5.6 package classifiers explicitly cover it, while
  this project host's Python 3.12 combination has not been runtime-verified.
- **Trade-off:** developers with only Python 3.12 can run core tests but need a
  Python 3.11 environment/container for Spark execution.
- **Sources:** [Spark 3.5.6 installation](https://spark.apache.org/docs/3.5.6/api/python/getting_started/install.html), [Spark 3.5.6 overview](https://spark.apache.org/docs/3.5.6/), [Delta compatibility](https://docs.delta.io/releases/).
