# Architecture

## Boundary

Ingestion adapters retrieve, normalize, validate, and envelope source events.
Kafka separates producers from Spark consumers and supports historical replay.
Spark Structured Streaming will perform the event-time transformations; it is
not replaced by pandas. Delta retains raw-to-analytical lineage, while
Elasticsearch serves the dashboard.

The concrete Bronze → Silver → Gold paths, keys, replay rules, and serving
boundary are defined in [the medallion architecture](medallion-architecture.md).

## Geographic normalization

`geography_dim` will hold canonical state/district IDs, aliases, validity
dates, and a versioned boundary reference. Flood geometry is intersected with
district polygons; mandi markets are mapped to canonical districts through a
curated market reference. Any unresolved mapping is a data-quality failure,
not a guessed join.

## Time semantics

`event_time` is when the observation/event occurred. `ingestion_time` is when
AgriShock received it. Temporal association and watermarks use event time;
ingestion time supports audit and operational latency metrics.
