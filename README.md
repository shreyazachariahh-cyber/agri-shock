# AgriShock

Real-time, event-time analytics for **potential agricultural distress-sale
signals**: unusual mandi price declines that occur after documented
environmental shocks and differ from historical/control-market movement.

## Scientific limitation

An alert is an explainable risk signal, not proof that weather or flooding
caused a price movement, farmer distress, or trader misconduct. Correlation is
not causation.

## Status

Phase 1 foundation complete. Local Docker is not installed, therefore Docker,
Kafka, Spark, Elasticsearch, and Kibana have not been run in this workspace.
See [data-source feasibility](docs/data-sources.md).

## Intended data flow

```text
Public sources / historical replay → Kafka → Spark Structured Streaming
→ Delta Bronze/Silver/Gold → Elasticsearch → Kibana
```

## Quick start (foundation)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python -m pytest
```

Copy `.env.example` to `.env` before configuring source credentials. Do not
commit `.env`.

## Project conventions

- Event time and ingestion time are distinct required fields.
- Invalid events are designed to become DLQ records with an explicit reason.
- Replayed historical data and synthetic failure tests are labelled as such.
- Geography is normalized to canonical IDs, not display-name joins.

## Documentation

- [Source validation](docs/data-sources.md)
- [Architecture](docs/architecture.md)
- [Data model](docs/data-model.md)
- [Engineering decisions](docs/engineering-decisions.md)
- [Limitations](docs/limitations.md)

## License

To be selected before public publication.
