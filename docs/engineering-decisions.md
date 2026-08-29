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

## No default watermark

- **Choice:** `watermark_hours` is unset in Phase 1.
- **Why:** a duration without source-lateness evidence would be arbitrary.
- **Next:** record observed source/fixture lateness, choose per-stream
  percentiles plus operational margin, and document beyond-watermark handling.
