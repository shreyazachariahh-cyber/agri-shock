# Multi-state recruiter demo fixture

`market_shock_signals.ndjson` is a **synthetic demonstration fixture**. Every
price, baseline, anomaly, control comparison, coordinate, confidence value, and
signal value in it was made for deterministic local replay and dashboard
demonstration. It is not sourced mandi data and must not be used to make a
claim about any district, market, commodity, farmer, or trader.

The five scenario labels provide varied geographic/event context only. They
are linked to public event references in [the demo runbook](../../docs/demo-runbook.md):
Assam flood, Bihar flood, Kerala flood, Maharashtra drought, and Himachal
Pradesh landslide. Before a real case study, replace each synthetic record
with a versioned, source-attributed extract and independently validate the
event geography and time range.

The fixture intentionally has two distinct districts and commodities per
state. It contains only `synthetic_demo` documents, a required field indexed
and exposed in Kibana so they cannot be mistaken for historical observations.
