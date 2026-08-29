# Data model

All events use `event_id`, `event_type`, `event_time`, `ingestion_time`,
`source`, `schema_version`, and `payload`.

| Event | Payload essentials |
|---|---|
| Mandi price | canonical geography, market, commodity, variety, unit, min/modal/max prices |
| Weather | canonical geography, actual/normal rainfall, departure percentage, IMD category |
| Flood | source event ID, start/end, geometry, source alert level, mapped districts |
| DLQ | original metadata, validation reason, failure stage, safely redacted raw reference |

Prices use decimal semantics in source-normalization code; source-specific
exceptions are retained as validation outcomes rather than silently coerced.
