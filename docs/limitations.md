# Limitations

- Signals are associations, not causal findings or claims about individual
  farmers/traders.
- IMD access is currently blocked from this project host.
- Historical source completeness must be proven before selecting a case study.
- Administrative boundaries and names change; mappings have temporal validity.
- Mandi data is commonly daily, so live ingestion does not imply intraday price
  discovery.
- The local WSL2 synthetic smoke workflow was live-validated, but this is not
  equivalent to a production-scale availability, load, or disaster-recovery test.
- The Phase 7 multi-state dashboard fixture is synthetic; event-context labels
  do not validate any listed market, coordinate, price, anomaly, or signal.
- Elasticsearch indexing was live-validated for the deterministic synthetic
  smoke signal; public-source throughput and failure-rate behavior remain
  unmeasured.
