# Interview preparation

## What problem does AgriShock solve?

It joins agricultural prices with environmental evidence across time and
geography to surface unusual market-price movements that warrant investigation.
It intentionally does not claim causation or prove farmer distress.

## Why Kafka?

Kafka decouples source/replay producers from Spark consumers, gives explicit
topics/partitions/offsets, and supports controlled historical replay.

## Why Spark Structured Streaming rather than pandas?

The core path needs stateful event-time processing, watermarks,
deduplication, and stream association. Pandas is not the streaming engine.

## Why Delta Lake and Bronze/Silver/Gold?

Bronze keeps raw evidence and Kafka metadata; Silver holds validated canonical
events and remediation/DLQ data; Gold contains associations and serving-ready
signals. Delta also supports schema enforcement, MERGE, and time-travelable
history.

## What is event time, and why are watermarks needed?

Event time is when the source observation occurred; ingestion time is when
AgriShock received it. Watermarks bound state for late/out-of-order events and
make that late-data policy explicit.

## How do you handle late or duplicate events?

Silver deduplicates stable event IDs within the configured watermark/state
contract. Stable Gold IDs, Delta MERGE, checkpoints, and Elasticsearch
document IDs prevent uncontrolled duplicate serving records during replay.

## What happens to malformed data?

Spark creates a DLQ envelope with the original payload, Kafka metadata,
processing time, stage, and reason. It is published to `dead-letter-events`
and persisted to `silver/dlq_events` for operations and health reporting.

## How is geography handled?

Geometry can be spatially associated with district references; market mappings
need authoritative versioned reference evidence. Unresolved or ambiguous
markets remain remediation records—never name guesses.

## How is the baseline constructed?

The implemented case uses the predeclared same-calendar-month median and MAD
for a market/commodity/variety/unit series. This avoids pooling varieties or
incompatible price units.

## Why median/MAD and robust z-score?

They are more resistant than mean/standard deviation to a few extreme price
observations. A robust z-score indicates unusualness relative to the baseline,
not why the price moved.

## Why Elasticsearch and Kibana?

Elasticsearch is the serving/search layer for deterministic Gold documents;
Kibana provides an inspectable dashboard with provenance and explanation.

## How does historical replay work?

Historical inputs retain original event time and are labelled
`replayed_historical`. Kafka/Spark process them through the same contracts;
the project never represents replay as continuous live operation in 2023.

## Why is the Vellore result LOW despite a high robust z-score?

The price moved upward, so the potential distress-sale decline component is
zero. The 144 ha source observation is not normalized severity, and no
authoritative unaffected control market was available. LOW is conservative and
correct.

## Does AgriShock prove farmer distress?

No. It produces observational early-warning signals that may warrant further
investigation; correlation does not prove cause, distress, or misconduct.

## What was the hardest engineering problem?

Reconciling source contracts without inventing geography: AGMARKNET reports
are stateful and can omit district, so the system preserves unresolved data
until authoritative, versioned reference evidence exists.

## What would you change for production?

Obtain governed nationwide market references and sustained source access, add
observed-lateness calibration, operate Spark/Kafka/Delta with production SLOs,
and validate scoring against a documented evaluation set—without changing the
non-causal framing.
