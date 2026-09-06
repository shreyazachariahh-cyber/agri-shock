# Kibana dashboard specification

Dashboard name: **AgriShock — market shock signal explorer (synthetic demo)**

Before building panels, create a data view named `agrishock-signals` over
`agrishock-market-shock-signals-*` with `event_time` as the time field. Apply
the pinned filter `fixture_kind: synthetic_demo` for the committed demo data.

## Panels

| Panel | Kibana visualization | Question answered | Configuration |
|---|---|---|---|
| Signal map | Maps / documents layer | Where are the replayed signals? | `location`; color by max `signal_strength`; tooltip state, district, commodity, level, confidence; never infer affected people from a point. |
| Active high signals | Metric + filter | Which contexts exceed the configured HIGH threshold? | Count where `signal_level: HIGH`; show `fixture_kind` beside it. |
| Signal ranking | Lens horizontal bar | Which district/commodity combinations have the largest signal strength? | Terms `district`, split by `commodity`; max `signal_strength`; filter out `INSUFFICIENT_EVIDENCE`. |
| Price vs baseline | Lens table | Is an observed price below its baseline in the replay? | Rows district/commodity; columns observed, baseline, deviation and robust z-score. |
| Shock timeline | Lens line/bar | How close is the price event to the shock time? | Time `event_time`, break down `shock_type`, metric max `signal_strength`. |
| Control comparison | Lens table | Does the local change differ from controls in the replay? | district, commodity, `control_difference_pct`, `deviation_pct`. |
| Explanation inspector | Discover saved search | Why did this record receive this level? | Include component scores, `data_confidence.value`, reasons, source references, and scenario note. |

## Guardrails

- Keep `fixture_kind` visible in the dashboard title or a Markdown panel.
- Do not title any panel “farmer distress,” “exploitation,” or “impact.”
- Display `data_confidence.value` and its reasons beside `signal_strength`.
- A map point represents a demo market coordinate, not a validated event extent
  or population impact.

## Index mapping

The indexer creates `agrishock-market-shock-signals-v1` from the strict
versioned mapping in
[`src/agri_shock/elasticsearch/indexer.py`](../../src/agri_shock/elasticsearch/indexer.py).
It maps `location` as `geo_point`, all identifiers/levels as `keyword`, event
times as `date`, numeric analytical fields as `double`, and component scores
as `flattened`.
