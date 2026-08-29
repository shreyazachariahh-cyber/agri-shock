# AgriShock contributor guide

## Scope and claim discipline

AgriShock emits **potential agricultural distress-sale signals**. It must never
claim that an environmental event caused farmer distress, price movements, or
trader exploitation.

## Data contract rules

- Preserve source `event_time` and system `ingestion_time` separately.
- Never label fixture, replay, or synthetic-failure data as live source data.
- Invalid records go to the dead-letter path with a reason; do not drop them.
- Use canonical geographic IDs; display names alone are never join keys.
- Keep secrets in environment variables, never commits.

## Engineering rules

- Use typed, small Python modules and test each data contract.
- Spark Structured Streaming owns streaming transformations; pandas is not a
  substitute for the core pipeline.
- Make watermarks, temporal windows, and scoring configuration-driven.
- Run relevant tests before committing. Do not state that Docker/Kafka/Spark
  integration works unless it was actually executed.
