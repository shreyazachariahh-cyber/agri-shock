# Market shock signal methodology

AgriShock emits a `MarketShockSignal`: an explainable statistical co-occurrence
between an environmental shock and unusual local market behavior. It is not
proof of flood causation, farmer distress, trader conduct, or exploitation.

## Signal strength

Strength is a 0–100 sum of configured, visible contributions: shock severity,
negative seasonal-baseline deviation, negative robust z-score magnitude,
post-shock temporal proximity, and affected-versus-control difference. The
policy is loaded explicitly from `SIGNAL_*` environment variables at runtime;
the development example is in `.env.example` and `config/app.yaml`.

| Component | Contribution rule | Provisional cap |
|---|---|---:|
| Shock severity | source/normalization severity in [0, 1] | 20 |
| Price decline | negative deviation, capped at 30 percentage points | 30 |
| Robust abnormality | negative robust z-score magnitude, capped at 3 | 20 |
| Temporal proximity | linear decay across the configured 14-day lookahead | 10 |
| Control difference | affected decline beyond the median control decline, capped at 20 percentage points | 20 |

The caps must sum to 100 and the HIGH/MEDIUM thresholds are configurable.
They are deliberately provisional, not empirically tuned claims. Median and
MAD are used because they are less sensitive than mean/standard deviation to
unusually large price observations. A zero MAD produces no robust-z claim and
therefore contributes zero robust-abnormality points.

Controls matter: a local decline that is much larger than comparable controls
adds strength; broadly similar decline does not. Signal levels are HIGH, MEDIUM,
LOW, or INSUFFICIENT_EVIDENCE. Thresholds are configuration policy, not tuned
to force dramatic historical outcomes.

## Data confidence

Confidence is separate from strength and is never multiplied into it. It uses
historical sample size, unique trading days, missing and duplicate rates,
canonicalized geography, control availability, known shock time, and required
field completeness. It records reasons such as `control_comparison_unavailable`
or `insufficient_historical_baseline`.

This supports honest combinations such as high strength with low confidence.
When baseline/geography/timing/required fields are insufficient, the output is
`INSUFFICIENT_EVIDENCE` rather than false precision.

## Gold analytical contract

The Phase 6 evaluator returns `MarketShockSignal`; the Phase 7 Elasticsearch
delivery contract accepts it with its join provenance as a Gold-like record.
The materialized production record will retain
the canonical `state_id`, `district_id`, optional `market_id` and
`commodity_id`, `shock_id`, `price_event_id`, `event_type`, `shock_time`,
`price_event_time`, `observed_price`, `baseline_price`, `deviation_pct`,
`robust_z_score`, `control_difference_pct`, `signal_strength`, `signal_level`,
component score map, `data_confidence`, confidence reasons, source references,
and processing/ingestion timestamps.

No field is interpreted as proof of farmer distress, source-event causation,
or trader behavior. A record may be high strength and low confidence; consumers
must show both values and their component/reason fields together.
