# Phase 13D pre-live execution

> Superseded as an execution gate by the successful Phase 13D live validation.
> This remains a historical pre-live decision record; the authoritative
> completed narrative is [the real case study](phase-13d-real-analytics.md).

## District-reported association

NRSC/NDEM's event is now associated through the exact authoritative pair
`reported_state + reported_district` against the versioned district reference.
The resulting association method is `source_reported_district`. It never uses
the reference MultiPolygon as event geometry. Geometry-based events retain the
distinct method `spatial_geometry_intersects`.

The Silver flood schema accepts the additional reported-district provenance
fields. Additive Delta schema evolution is explicitly allowed only for that
sink and the changed Gold-association sink; it is not enabled globally.

## Control selection contract (fixed before outcomes)

A prospective control must satisfy every requirement below before any price
outcomes are examined:

1. official AGMARKNET-backed State → District → Market reference evidence;
2. district outside the NRSC/NDEM affected-district evidence for this event;
3. same commodity and compatible, row-level documented price unit;
4. enough pre-event same-calendar-month history for the existing median/MAD
   baseline policy, with sufficient distinct trading days;
5. observations covering the same post-event analytical window;
6. no unresolved or ambiguous market/district mapping; and
7. recorded source URL, retrieval date, data-quality rates, and reference
   snapshot version.

No control is selected in Phase 13D pre-live work. The locally preserved
AGMARKNET extract is a Tamil Nadu Onion sample for Thammampatti, not a
district-resolved Vellore Paddy series or a suitable comparison set. It must
not be repurposed as a Vellore result.

## Analytics wiring audit

The repository has tested library contracts for seasonal median/MAD baselines,
robust z-scores, controls, confidence, scoring, Gold contracts, Delta merge,
and Elasticsearch idempotent delivery. The production streaming app currently
materializes only Gold shock-price associations; it does **not** materialize
real baselines, anomalies, controls, or MarketShockSignals. Its only Gold
signal materializer is intentionally synthetic smoke-test code.

Therefore no real MarketShockSignal can yet be claimed. This is not a failed
signal: real Vellore historical price observations, a qualified control (or a
documented no-control path), and a production analytical materializer are
required before live execution. The NRSC inundated-area measurement remains
unscored because the configured scoring contract has no justified conversion
to a 0–1 shock severity.

## Live prerequisites

Before any real run, prepare Delta market and boundary reference tables from
the bounded snapshots, acquire and validate actual Vellore APMC Paddy(Common)
AGMARKNET records and sufficient historical observations, and either qualify a
control under the contract above or preserve the absence of one. Do not use the
district boundary as a substitute flood footprint.
