# Geographic reference-data contracts

The association pipeline is geography and commodity agnostic. It does not ship
with a Vellore/Tomato or any other locality-specific production mapping.

## Market dimension

The Delta input at `MARKET_DIMENSION_PATH` must contain:

| Field | Meaning |
|---|---|
| `source_state` / `source_district` / `source_market` | values as reported by the source, curated into a reference table |
| `state_id` / `district_id` / `market_id` | stable canonical identifiers |

Source display values only resolve through this explicit versioned reference;
they are not used as analytical joins.

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
