# Demo guide

## 30-second explanation

“AgriShock is an event-time streaming platform for investigating whether an
environmental shock is followed by an unusual local agricultural-price movement.
Kafka carries source and replay events; Spark Structured Streaming validates,
deduplicates, and associates them; Delta preserves Bronze, Silver, and Gold
lineage; Elasticsearch and Kibana make the resulting signal explainable. It
produces observational market-shock evidence, not a causal distress claim.”

## 60–90 second dashboard walkthrough

1. Open the **AgriShock — Vellore real historical case** dashboard. Point out
   the pinned `replayed_historical` provenance and deterministic signal filter.
2. Introduce the bounded case: Cyclone Michaung, Vellore, December 2023;
   Vellore APMC, Paddy(Common), `Other`, Rs./Quintal.
3. Compare the 04-Dec modal price of ₹2,993 with the fixed December 2022
   median of ₹1,851 from 22 variety-specific observations.
4. Explain that +61.7% and +6.37 robust z-score mean unusual movement, not
   cause or distress. The movement is positive, not a decline.
5. Explain why the result is LOW: decline contribution is zero; 144 ha is not
   normalized severity; no authoritative unaffected control was captured.
6. Close with delivery evidence: 96 Bronze, 95 Silver mandi, one Silver flood,
   11 associations, one deterministic Gold signal, then Elasticsearch/Kibana.

## 2–3 minute technical walkthrough

1. **Why Kafka and Spark:** producers and replay are decoupled from stream
   consumers; Spark provides schema-aware stateful event-time processing,
   watermarks, and temporal association—not a pandas batch loop.
2. **Why Bronze/Silver/Gold:** Bronze preserves raw Kafka coordinates and
   payloads; Silver carries validated canonical IDs and durable DLQ records;
   Gold serves associations and a transparent MarketShockSignal.
3. **Correctness:** stable event/signal identities, targeted Delta MERGE,
   checkpoints, and Elasticsearch `_id=signal_id` make documented replays
   idempotent. Invalid records go to Kafka and Delta DLQ representations.
4. **Geography and time:** canonical mappings are authoritative or unresolved;
   event time, not arrival time, determines shock-price association.
5. **Analytics:** the baseline uses median/MAD for robustness. Signal strength
   and data confidence are separate. A missing control remains missing rather
   than being guessed.
6. **Real result:** this one bounded replay verified the end-to-end mechanics,
   but does not claim live production operation or causal impact.

## Before presenting

- Use the real dashboard, not the synthetic demo.
- Confirm the dashboard query includes `fixture_kind: replayed_historical`.
- Do not call 144 ha a severity score or a flood footprint.
- Do not describe LOW as a failure or the result as farmer distress.
