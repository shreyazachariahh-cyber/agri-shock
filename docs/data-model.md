# Data model

All events use `event_id`, `event_type`, `event_time`, `ingestion_time`,
`source`, `schema_version`, and `payload`.

| Event | Payload essentials |
|---|---|
| Mandi price | canonical geography, market, commodity, variety, unit, min/modal/max prices |
| Weather | canonical geography, actual/normal rainfall, departure percentage, IMD category |
| Flood | source event ID, start/end, geometry, source alert level, mapped districts |
| DLQ | original metadata, validation reason, failure stage, safely redacted raw reference |
| Market shock signal (Gold) | canonical state/district/market/commodity IDs, shock and price provenance, event/processing times, baseline/anomaly/control fields, model-contract version, signal strength/level, component scores, and separate data confidence/reasons |

Prices use decimal semantics in source-normalization code; source-specific
exceptions are retained as validation outcomes rather than silently coerced.

The analytical output uses `signal_strength`, `signal_level`, and
`data_confidence`; it intentionally avoids a distress-oriented score field.

The authoritative physical-table and replay contracts are in
[the medallion architecture](medallion-architecture.md).
