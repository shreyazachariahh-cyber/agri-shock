# Geographic matching

Flood geometry is converted to a district association only through a versioned
district-boundary dataset: `ST_Intersects(flood_geometry, district_geometry)`
in the Spark/Sedona production path. Point-only sources use `ST_Contains`.
Market records map through a curated market-to-canonical-district reference.

Display names are evidence for curation, never join keys. Results retain the
canonical district ID, match method, boundary version, and mapping confidence.
Zero/multiple matches are rejected to DLQ or marked unresolved; they are never
silently assigned. The test implementation uses ray casting; it is not a
substitute for Sedona in production.

The temporal association joins price observations in the inclusive interval
`[shock_time, shock_time + SHOCK_LOOKAHEAD_DAYS]`, after both sides receive
event-time watermarks. This is an association window, not causal evidence.
