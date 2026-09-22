# Phase 13D historical coverage checkpoint

This is a data-availability checkpoint for the selected Tamil Nadu / Michaung
/ Vellore case. It does not run anomaly scoring, streaming, or create a
MarketShockSignal.

## Predeclared batch and source gaps

The official AGMARKNET State daily reports represented 01, 02, 03, 04, 05,
07, 08, and 11 December 2023. The official portal reported **no data
available** on 06 December; that source-availability gap is retained rather
than represented as zero arrivals or a filled observation.

For the pre-event calculation, the documented Michaung conditions beginning
on 03 December are used as the exclusive cutoff: only observations before
`2023-12-03` are eligible. This applies the existing calendar-month baseline
contract and does not make post-event data baseline history.

The raw 05-Dec artifact contains `Vellore APMC`, but its rows are Copra,
Groundnut, and Spinach. Its `Paddy(Common)` / `ADT 37` row belongs to
`Vikkiravandi APMC`, not Vellore. The raw official artifact therefore controls
over the earlier high-level acquisition note: 05-Dec is recorded as a Vellore
Paddy availability gap, not as a Vellore ADT 37 observation.

## Vellore APMC / Paddy(Common) coverage

All accepted rows explicitly report `Rs./Quintal`. No varieties were pooled.

| Variety | Dates represented | Total observations | Pre-event observations |
|---|---|---:|---:|
| ADT 37 | 04, 11 Dec | 2 | 0 |
| Co. 43 | 07 Dec | 1 | 0 |
| HMT | 01 Dec | 1 | 1 |
| I.R. 50 | 01, 11 Dec | 2 | 1 |
| Other | 01, 04, 07, 08, 11 Dec | 5 | 1 |
| Ponni | 11 Dec | 1 | 0 |
| Sona | 07, 08 Dec | 2 | 0 |

There are 14 accepted target observations, zero target-row validation
rejections, and no qualifying variety: the established minimum is five
**pre-event** same-calendar-month observations. `Other` has five observations
in total, but four are on/after the event cutoff and are excluded.

## Data-quality evidence

- Reports for 02, 03, and 05 December contain no Vellore APMC / Paddy(Common)
  row.
- 06 December has no official report because the portal returned no data.
- The report format is stateful; blank commodity fields are parsed only using
  the immediately preceding explicit commodity context.
- District is supplied only by the bounded, official Vellore case reference;
  it is not inferred from the price report.

## Next predeclared acquisition window

Do not choose isolated dates after seeing prices. The smallest systematic next
window is **all available Tamil Nadu state-daily reports from 01–31 December
2022**, filtered only after import to the already-fixed Vellore APMC /
Paddy(Common) / variety / `Rs./Quintal` identities. It is an earlier fixed
calendar month, so it is compatible with the current baseline's seasonal rule
and can supply prior observations without treating post-event December 2023
rows as baseline data. Whether any variety reaches five observations remains
an empirical coverage question.

## Baseline-method assessment (no production change)

The current same-calendar-month median/MAD design is reasonable as a simple
seasonality guardrail, but its suitability for sparse mandi reporting remains
unvalidated. A future methodology review may evaluate a documented crop
marketing-season or calendar-window baseline across prior years, with an
externally sourced commodity calendar and held-out tests. This is a proposal
only: no baseline, confidence threshold, or signal logic changed in this
checkpoint.
