# Phase 13B — real case-study selection

> Historical selection checkpoint. The selected Vellore case completed live
> validation in Phase 13D/E; its final metrics and scientific interpretation
> are in [the completed case study](phase-13d-real-analytics.md). This file
> preserves the pre-outcome selection rationale.

## Decision rule

Phase 13B selects a case for reproducibility and analytical feasibility, not
for the magnitude or direction of any observed price movement. The criteria
were fixed before inspecting outcomes:

1. authoritative environmental-event evidence;
2. bounded event date/window and affected geography;
3. official mandi-price availability before, during, and after the window;
4. plausible historical baseline, commodity/variety continuity, and compatible
   price units;
5. potential same-commodity controls outside documented affected geography;
6. ability to create a small authoritative State → District → Market snapshot;
7. retrieval reproducibility, schema stability, missingness, and implementation
   complexity.

`HIGH`, `MEDIUM`, `LOW`, `INSUFFICIENT_EVIDENCE`, and no unusual movement are
all valid later outcomes. None is a selection criterion.

## Candidate A — Tamil Nadu, Cyclone Michaung flooding, December 2023

### Environmental evidence

- IMD's [Michaung post-event report](https://rsmcnewdelhi.imd.gov.in/images/rainfall.pdf)
  records heavy through extremely heavy rainfall over north coastal Tamil Nadu
  on 3–4 December 2023.
- The official [NRSC/NDEM rapid flood assessment](https://ndem.nrsc.gov.in/documents/Disaster_Document/2023/TN/tncyclone50dsc07122023_0600hrs/tncyclone50dsc07122023_0600hrs_report.pdf)
  identifies flooding from the first week of December and lists affected
  districts, including Vellore. Its 7 December satellite assessment reports
  144 hectares of mapped inundation in Vellore and cautions that this is a
  rapid, preliminary map without ground verification.
- The Tamil Nadu Government's [December 2023 gazette listing](https://www.stationeryprinting.tn.gov.in/extra_ordinary_lists.php?id=MjAyMw%3D%3D)
  separately records government actions for Michaung-affected districts. It is
  supporting context, rather than a substitute for the flood map.

**Event definition for the future study:** Michaung-related heavy-rain and
flood conditions from 3–7 December 2023, anchored to the cyclone's 5 December
crossing. This is an association window, not a causal claim.

### Bounded price-coverage check

The official AGMARKNET Market-wise, Commodity-wise Daily Report for State/UT
was queried for Tamil Nadu on 20 November, 4 December, and 18 December 2023.
Each returned `Vellore APMC` and `Paddy(Common)` observations with an explicit
`Rs./Quintal` price unit. These three dates establish baseline-window,
event-window, and 14-day post-window source availability only. They are not a
coverage count, price trend, or price-effect assessment. A full bounded audit
is deferred until the case-reference snapshot exists.

The report's stateful rows and heterogeneous units remain material data-quality
constraints. Only rows with compatible units may enter a numerical comparison.

### Geography and controls

`Tamil Nadu → Vellore → Vellore APMC` is **likely resolvable, but not yet
canonical**. The required next artifact is a small, versioned, official-source
reference snapshot for the selected affected market and selected controls. It
must retain source reference, retrieval date, scope, and any official ID; it
must not be inferred from matching display names.

The state report shows multiple markets and common commodities. This makes
same-commodity controls **plausible**, but no control market is designated
until its district is independently evidenced and confirmed outside the
documented affected geography.

## Candidate B — Himachal Pradesh monsoon flooding, July 2023

### Environmental evidence

- The [Himachal Pradesh State Disaster Management Authority investigation
  index](https://hpsdma.hp.gov.in/Contents.aspx?langid=1&lev=3&lid=5353&lsid=8998&pid=5106)
  provides district-specific investigation reports for the 2023 monsoon,
  including Kullu, Shimla, Solan, Kinnaur, Hamirpur, and Mandi.
- IMD agricultural-services material identifies 7–11 July 2023 as a major
  rainfall spell and names Kinnaur, Kullu, Solan, Bilaspur, Shimla, and Sirmaur
  among the most affected districts. This provides a clear regional event
  period, while also demonstrating a broad and heterogeneous impact footprint.

### Bounded price-coverage check

Phase 13A verified that AGMARKNET returned real Himachal Pradesh observations
for 10 July 2023 across multiple markets and commodities, with heterogeneous
row-level units. This is sufficient to establish source availability but not
to establish continuous pre/post coverage for any district-resolved market.

### Geography and controls

The observed AGMARKNET market labels have not yet been independently tied to
districts through a bounded official reference snapshot. The monsoon footprint
also spans many market-relevant districts, making unaffected-control selection
more constrained than in the Tamil Nadu candidate. This candidate remains a
valid future extension, but its geography/control feasibility is weaker today.

## Feasibility comparison

| Criterion | Tamil Nadu / Michaung / Vellore | Himachal Pradesh / July monsoon |
|---|---|---|
| Authoritative event evidence | **STRONG** — IMD plus NRSC flood assessment | **STRONG** — IMD plus HPSDMA reports |
| Bounded event window | **STRONG** — 3–7 Dec 2023 | **STRONG** — 7–11 Jul 2023 |
| Affected geography | **STRONG** — named districts and flood-map estimate | **STRONG** — named districts, broader multi-district footprint |
| Around-event price availability | **STRONG** — Vellore APMC/Paddy(Common) found on three bounded dates | **ACCEPTABLE** — multi-market availability confirmed for 10 Jul |
| Baseline feasibility | **ACCEPTABLE** — source supports historical queries; full audit pending | **UNKNOWN** — full district-resolved audit pending |
| Unit compatibility | **ACCEPTABLE** — qualifying quintal rows observed; mixed units must be filtered | **ACCEPTABLE** — qualifying quintal rows exist; mixed units present |
| Geography resolution | **ACCEPTABLE, conditional** — small official snapshot required | **WEAK, conditional** — small official snapshot required for every participant |
| Control-market feasibility | **ACCEPTABLE, conditional** — broad state report and narrower documented footprint | **WEAK** — broad affected footprint constrains controls |
| Retrieval reproducibility | **ACCEPTABLE** — session-backed official reports plus manifest/raw-export requirement | **ACCEPTABLE** — same report constraints |
| Overall implementation complexity | **ACCEPTABLE** | **WEAK** |

## Selected case

**Tamil Nadu — Cyclone Michaung-related flooding, Vellore district, December
2023** is selected for implementation planning.

It is selected because the event has complementary authoritative weather and
flood evidence, a concrete affected district in the official flood assessment,
and a bounded affected market/commodity availability check spanning before,
during, and after the event. It also has a more plausible path to a narrow
control design. It was **not** selected because of any price movement.

Himachal Pradesh July 2023 is retained as a documented future extension. It
has strong event evidence, but the currently broader affected geography and
unresolved market-to-district evidence make its first reproducible control
design more difficult.

## Phase 13B completion and prerequisite

Phase 13B is complete. No final price outcomes were inspected for selection;
only report availability, schema, unit, market, and date coverage were checked.

Before Phase 13C, create and validate a **bounded authoritative reference
snapshot** for `Tamil Nadu → Vellore → Vellore APMC` and any prospective
control markets, plus the corresponding versioned district-boundary input.
The snapshot must be provenance-backed, versioned, and scoped to this case. If
that evidence cannot be captured, the case must remain unresolved rather than
fall back to display-name inference.
