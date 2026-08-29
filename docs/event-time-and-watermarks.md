# Event time and watermarks

`event_time` records when the source observed a price/weather/flood event;
`ingestion_time` records when AgriShock received it. Every analytical window,
deduplication operation, and later temporal join uses event time.

The pipeline refuses to choose a default watermark. Phase 3 exposes an explicit
positive `EventTimePolicy`, but deployment must set it only after observing
source lateness. The measurement plan is to retain ingestion minus event-time
lags by source, choose a documented coverage percentile plus operational margin,
and record the state-retention cost. Events beyond the chosen watermark may be
preserved in Bronze/DLQ but will not update stateful stream results; periodic
batch reconciliation remains the corrective path.
