# Phase 14 — dashboard and demo experience

## Purpose

The primary Kibana dashboard presents the completed Vellore / Cyclone Michaung
case as a **replayed historical** validation of AgriShock's general pipeline.
It explains the observation, model evidence, confidence, and limitations—not
a causal impact claim.

## Dashboard design

The dashboard is provisioned from
[`dashboards/kibana/agri_shock_real_historical.ndjson`](../dashboards/kibana/agri_shock_real_historical.ndjson).
Its data view is `agrishock-market-shock-signals-*`, and its query pins
`fixture_kind: replayed_historical` plus the deterministic Vellore signal ID.
Synthetic smoke data is excluded by default.

| Panel | Purpose |
|---|---|
| Header | AgriShock, Vellore, Cyclone Michaung, December 2023, and replayed-historical provenance. |
| Status / strength / confidence / associations | Makes LOW, 9.29 strength, 87.5% confidence, and 11 verified associations immediately visible. |
| Observed versus baseline | Compares ₹2,993 observed with ₹1,851 historical median from the 22-observation fixed baseline. |
| Price movement / historical unusualness | Shows +61.7% and +6.37 as unusual movement, not distress proof. |
| LOW explanation | Makes absent decline, normalized severity, and control explicit. |
| Pipeline evidence | Records 96 Bronze, 95 Silver mandi, 1 Silver flood, 11 associations, one Gold signal. |

No map panel is used: the Gold document intentionally has no event coordinate.
A point map would misleadingly imply a precise flood footprint or market
coordinate. Runtime-health counts are not fabricated as live Kibana metrics.

## Reproducible provisioning

```powershell
python scripts/provision_kibana_dashboard.py --validate-only
python scripts/provision_kibana_dashboard.py --url http://localhost:5601
```

The provisioner is idempotent at saved-object identity level. It does not
alter Elasticsearch signal documents. The compact dashboard layout deliberately
puts case → signal → observed versus baseline → anomaly → interpretation →
pipeline evidence in that order; manual panel construction is not required.

## 60–90 second walkthrough

1. “AgriShock streams agricultural price and environmental events through
   Kafka and Spark, then preserves Bronze, Silver, Gold, and searchable signal
   layers.”
2. “This is the first real historical validation case: Cyclone Michaung,
   Vellore, and Vellore APMC's Paddy(Common) `Other` variety.”
3. “The dashboard is explicitly filtered to replayed historical evidence; the
   synthetic smoke record is excluded.”
4. “The observed 04-Dec price was 2993 Rs./Quintal against a fixed Dec-2022
   median baseline of 1851: +61.7% and a +6.37 robust z-score.”
5. “That is not a distress claim. The movement is upward rather than a decline,
   so the potential distress-sale price-decline component is zero.”
6. “NRSC/NDEM reports 144 hectares, but AgriShock does not pretend that is a
   normalized severity score. No authoritative unaffected control was found.”
7. “The result is LOW strength, 9.29, with 0.875 confidence—an explainable,
   conservative outcome rather than an inflated alert.”
8. “The signal followed 96 Bronze, 95 Silver mandi, one Silver flood, and 11
   temporal/geographic associations before Gold and Elasticsearch.”

## Screenshot plan

Capture only after visually checking the provisioned dashboard; do not commit
placeholder imagery.

1. **Dashboard hero:** full Vellore dashboard with provenance and LOW panel.
2. **Price evidence:** observed/baseline, deviation, robust-z panels.
3. **Scientific safeguards:** LOW explanation with confidence/control context.
4. **Engineering proof:** pipeline panel beside terminal or Delta/Elasticsearch
   verification output, labelled as recorded live validation.

Every screenshot must retain `REPLAYED HISTORICAL` and must not present the
synthetic Dhemaji record as real evidence.
