# Kibana dashboards

## Primary dashboard: real historical case

[`agri_shock_real_historical.ndjson`](agri_shock_real_historical.ndjson) is a
version-controlled Kibana 8.15 saved-object bundle. Its primary dashboard is
**AgriShock — Vellore real historical case**.

It pins both `fixture_kind: replayed_historical` and the verified Vellore
signal ID `70ad06f7c3b849dd56b870c77f9dff20d187c802ec2d6c0eea7374f92b9e6c79`.
This prevents the existing `synthetic_demo` Dhemaji smoke record from appearing
as real evidence. The data view targets `agrishock-market-shock-signals-*`,
using `event_time` as its time field.

The first viewport presents case/provenance, a prominent LOW status, signal
strength, 87.5% evidence confidence, and 11 verified associations. It then
compares ₹2,993 observed price with the ₹1,851 historical median before
showing deviation, robust anomaly, the conservative LOW-result explanation,
and recorded pipeline evidence. The association count is an annotated Phase
13D validation result, not a fabricated live metric.

## Provisioning

With Kibana running locally, validate then provision the bundle:

```powershell
python scripts/provision_kibana_dashboard.py --validate-only
python scripts/provision_kibana_dashboard.py --url http://localhost:5601
```

The script uses Kibana's saved-object API with explicit object IDs and
`overwrite=true`, so rerunning it updates the version-controlled bundle rather
than creating anonymous duplicates. It does not import Elasticsearch documents
or modify Gold data.

Open Kibana and select **Dashboard → AgriShock — Vellore real historical
case**. Retain its default Dec 2023 time range and pinned real-historical
filter.

## Synthetic technical demo

The existing synthetic fixture remains available for a separate technical
demo: [demo runbook](../../docs/demo-runbook.md). It must use
`fixture_kind: synthetic_demo` and be labelled **Synthetic demo data — not a
real market finding**. Do not combine it with the primary real-case dashboard.

## Interpretation guardrails

- The Vellore district polygon is reference geography, not a flood footprint.
- NRSC/NDEM's 144 ha is observed inundation, not normalized severity.
- The positive price movement and robust anomaly do not establish causality or
  farmer distress.
- LOW is intentional: no price decline, no normalized severity contribution,
  and no authoritative control comparison.
