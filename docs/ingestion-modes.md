# Ingestion modes

## Live public source

`python -m agri_shock.ingestion.run mandi --mode live` retrieves the endpoint
set in `MANDI_API_URL` and publishes valid envelopes to Kafka. Weather and flood
use `IMD_API_URL` and `GDACS_API_URL`. URLs/credentials remain environment
configuration. Source requests use bounded exponential retries and timeouts.

## Replayed historical data

`python -m agri_shock.ingestion.run mandi --mode replay --file PATH` replays
only NDJSON labelled `replayed_historical` or `synthetic_failure_injection`.
Original `event_time` is retained while ingestion speed is controlled by
`--events-per-second`.

## Synthetic failure injection

The committed fixture under `data/fixtures/synthetic_failure_injection/` is
intentionally invalid and exists only to exercise validation/DLQ behavior. It
is not real market data.

## Current source status

Public endpoints remain subject to the documented IMD IP restriction and the
historical coverage limitations in `docs/data-sources.md`. A failed live call
raises a visible error; it is never replaced with fabricated records.
