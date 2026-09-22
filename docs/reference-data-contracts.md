# Geographic reference-data contracts

The association pipeline is geography and commodity agnostic. It does not ship
with any locality- or commodity-specific production mapping.

## Market dimension

The Delta input at `MARKET_DIMENSION_PATH` must contain:

| Field | Meaning |
|---|---|
| `source_state` / `source_district` / `source_market` | values as reported by the source, curated into a reference table |
| `state_id` / `district_id` / `market_id` | stable canonical identifiers |

Source display values only resolve through this explicit versioned reference;
they are not used as analytical joins.

### Bounded case-study references

A case study may ship a small `case-study reference data` snapshot only when
each State → District → Market relationship has row-level official evidence.
Its scope, retrieval time, evidence URL, and identifier basis are mandatory.
Canonical IDs may be deterministic AgriShock IDs when an official identifier
is not exposed; they must not be represented as government IDs. Exact matching
and unique State + Market records are required. A bounded snapshot is never a
nationwide AGMARKNET master and an absent or ambiguous market remains
unresolved.

## District boundary dimension

The Delta input at `DISTRICT_BOUNDARY_PATH` must contain `district_id`,
`source_state`, `source_district`, and WGS84 `geometry_json`. Flood event
GeoJSON is spatially intersected with these district geometries using Sedona.

## Relationships and provenance

The Gold association retains `district_id`, `market_id`, `commodity_id`,
`shock_id`, `shock_type`, `shock_time`, `price_event_time`,
`days_after_shock`, and `spatial_relationship`. Current relationships are
`same_district`; future reference datasets may add `adjacent_district` and
`nearby_market` with documented criteria. Unmatched records are not guessed.

The final case-study selection will measure coverage across state, district,
market, commodity, and event before choosing any real dataset.
