# Phase 13D — Vellore real historical analytics

This bounded case uses real, manually preserved official AGMARKNET reports and
NRSC/NDEM evidence. It is a replayed-historical market-shock analysis, not a
causal finding about flooding, farmer distress, or any participant's conduct.

## Fixed study inputs

- **Target:** Vellore APMC / `Paddy(Common)` / `Rs./Quintal`.
- **Environmental evidence window:** 03–07 Dec 2023. NRSC/NDEM reports
  Vellore as a source-reported district with 144 hectares of observed
  inundation. That quantity is retained as provenance and is not converted to
  a normalized severity score.
- **Baseline window:** all Tamil Nadu state-daily reports from 01–31 Dec 2022,
  declared and acquired before anomaly results were examined.
- **Baseline method:** existing same-calendar-month median/MAD contract with a
  minimum of five observations. Varieties and price units are never pooled.

## Outcome-independent target selection

A series is eligible only when it has the exact target market/commodity/unit,
at least one observation in the evidence window, and at least five rows in
the fixed baseline window. The selection is the eligible variety with the
greatest historical observation count; a lexical variety-name tie breaker is
used. No price value, price change, anomaly, or prospective signal affects
this rule.

The real local run selected **Other**: 22 historical rows and two event-window
rows. `ADT 37` was also eligible (15 historical rows, one event-window row).
`HMT`, `I.R. 50`, `Ponni`, and `White Ponni` were not observed in the event
window; `Co. 43` and `Sona` lacked the minimum historical coverage.

## Computed local analysis artifact

`agri_shock.runtime.real_case` reads only labelled `replayed_historical`
envelopes, rejects conflicting event IDs, and writes a gitignored local JSON
artifact. Its first eligible event-window observation is selected by timestamp
and event ID, before calculating an anomaly. For the current preserved
artifacts, that is 04 Dec 2023, `Other`, modal price **2993.0 Rs./Quintal**.

The fixed December 2022 baseline is **22** observations, median **1851.0**,
and MAD **121.0**. The derived percentage deviation is **+61.6964%** and the
robust z-score is **+6.3659**. These figures describe the series relative to
its limited historical baseline; they do not indicate a price decline or
demonstrate a distress sale.

No authoritative unaffected control market and matching evidence have been
captured. Therefore `control_difference_pct` remains null and
`control_comparison_unavailable` is retained in data confidence. The signal
uses a zero environmental severity contribution because the observed 144 ha is
not a valid 0–1 severity measure. Under the existing signal policy the result
is **LOW**, strength **9.29**, data confidence **0.875**; it remains a
potential market-shock signal only.

## Live replay preparation

The runtime uses bounded Delta reference dimensions created from the existing
case-study market snapshot and transformed official district reference
geometry. The boundary supplies an identity key only; it is not treated as an
inundation footprint. The district-reported association derives its temporal
join clock from the explicit source `event_start`, while Bronze/Silver retain
the NRSC observation time unchanged.

For this historical replay, use a deliberately long, case-specific watermark
so 2022 baseline input is not evicted before the 2023 replay reaches the
event window. This is a replay-state-retention setting, not a new production
watermark recommendation. The real Gold materializer uses the canonical Gold
schema, deterministic `(shock_id, price_event_id)` identity, Delta MERGE, and
Elasticsearch `_id=signal_id`; replays therefore do not create duplicate
serving rows.

## Live validation evidence

The real historical validation was run in WSL on 05 Oct 2026 using the bounded
case reference dimensions and the preserved local artifacts. Kafka accepted the
replayed historical flood event and 95 mandi observations. The streaming query
persisted 96 Bronze records, 95 Silver mandi records, and one Silver flood
record. A direct Delta inspection then found **11** Gold shock-price
associations; these are distinct price-event associations, not 11 final
signals.

The real Gold materializer persisted exactly one row for
`70ad06f7c3b849dd56b870c77f9dff20d187c802ec2d6c0eea7374f92b9e6c79` and
indexed that same ID into Elasticsearch. The serving index contained two
different documents: the real Vellore signal and the pre-existing labelled
synthetic smoke signal `d63e43c17095a70ff7628fb416598be085adb0bad6c9fd861e598db8dacdf68c`.
That is expected shared-index state, not a duplicated real signal.

An earlier `runtime.health` read showed zero Gold associations while the
association streaming sink was still catching up. A later direct Delta read
showed 11. `runtime.health` is deliberately a read-only point-in-time snapshot,
not a completion barrier; operators should run it after Spark progress has
settled or use the deterministic real-case verifier for the target Gold and
Elasticsearch identity. No health-counting defect or replay duplication was
found.

The exact live commands are supplied in the Phase 13D report. This validation
confirms delivery mechanics and analytical reproducibility; it does not turn
the LOW signal into causal evidence of flooding, farmer distress, or market
misconduct.
